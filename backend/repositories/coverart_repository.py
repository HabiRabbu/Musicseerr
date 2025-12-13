import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from urllib.parse import quote

import aiofiles
import httpx

from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from infrastructure.validators import validate_mbid
from infrastructure.queue.priority_queue import RequestPriority, get_priority_queue
from infrastructure.http.deduplication import RequestDeduplicator

if TYPE_CHECKING:
    from repositories.musicbrainz_repository import MusicBrainzRepository
    from repositories.lidarr_repository import LidarrRepository

logger = logging.getLogger(__name__)

COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"
DEFAULT_CACHE_DIR = Path("/app/cache/covers")

_coverart_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="coverart"
)

_deduplicator = RequestDeduplicator()

VALID_IMAGE_CONTENT_TYPES = frozenset([
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/avif",
    "image/svg+xml",
])


def _is_valid_image_content_type(content_type: str) -> bool:
    if not content_type:
        return False
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in VALID_IMAGE_CONTENT_TYPES


def _get_cache_filename(identifier: str, suffix: str = "") -> str:
    content = f"{identifier}:{suffix}"
    hash_digest = hashlib.sha1(content.encode()).hexdigest()
    return hash_digest


class CoverArtRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
        mb_repo: Optional['MusicBrainzRepository'] = None,
        lidarr_repo: Optional['LidarrRepository'] = None,
        cache_dir: Path = DEFAULT_CACHE_DIR
    ):
        self._client = http_client
        self._cache = cache
        self._mb_repo = mb_repo
        self._lidarr_repo = lidarr_repo
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def _write_disk_cache(
        self,
        file_path: Path,
        content: bytes,
        content_type: str,
        extra_meta: Optional[dict[str, str]] = None,
        is_monitored: bool = False,
    ) -> None:
        try:
            import json
            from datetime import datetime
            
            now = datetime.now().timestamp()
            ttl = None if is_monitored else 24 * 3600
            
            meta = {
                'content_type': content_type,
                'created_at': now,
                'last_accessed': now,
                'size_bytes': len(content),
                'is_monitored': is_monitored
            }
            
            if ttl:
                meta['expires_at'] = now + ttl
            
            if extra_meta:
                meta.update(extra_meta)
            
            async def write_content():
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(content)
            
            async def write_meta():
                async with aiofiles.open(f"{file_path}.meta", "w") as m:
                    await m.write(json.dumps(meta))
            
            async def write_wikidata():
                if extra_meta and 'wikidata_id' in extra_meta:
                    async with aiofiles.open(f"{file_path}.wikidata_id", "w") as wf:
                        await wf.write(extra_meta['wikidata_id'])
            
            await asyncio.gather(write_content(), write_meta(), write_wikidata())
        
        except Exception as e:
            logger.warning(f"Failed to write disk cache: {e}")
    
    async def _read_disk_cache(
        self,
        file_path: Path,
        extra_keys: Optional[list[str]] = None,
    ) -> Optional[tuple]:
        try:
            import json
            from datetime import datetime
            
            meta_file = Path(f"{file_path}.meta")
            if not file_path.exists() or not meta_file.exists():
                return None
            
            async def read_content():
                async with aiofiles.open(file_path, "rb") as f:
                    return await f.read()
            
            async def read_meta():
                async with aiofiles.open(meta_file, "r") as m:
                    return await m.read()
            
            content, meta_content = await asyncio.gather(read_content(), read_meta())
            
            try:
                meta = json.loads(meta_content)
                content_type = meta.get('content_type', 'image/jpeg')
                
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Disk cache contains non-image ({content_type}), treating as miss")
                    return None
                
                expires_at = meta.get('expires_at')
                if expires_at and datetime.now().timestamp() > expires_at:
                    return None
                
                meta['last_accessed'] = datetime.now().timestamp()
                asyncio.create_task(self._update_meta_access(meta_file, meta))
                    
            except (json.JSONDecodeError, ValueError):
                content_type = meta_content.strip()
            
            result = [content, content_type]
            
            if extra_keys:
                async def read_extra_key(key: str):
                    try:
                        async with aiofiles.open(f"{file_path}.{key}", "r") as f:
                            return (await f.read()).strip()
                    except FileNotFoundError:
                        return None
                
                extra_values = await asyncio.gather(*[read_extra_key(k) for k in extra_keys])
                result.extend(extra_values)
            
            return tuple(result)
        
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Disk cache read error: {e}")
            return None
    
    async def _update_meta_access(self, meta_file: Path, meta: dict) -> None:
        try:
            import json
            async with aiofiles.open(meta_file, "w") as m:
                await m.write(json.dumps(meta))
        except Exception:
            pass
    
    @with_retry(max_attempts=3, circuit_breaker=_coverart_circuit_breaker)
    async def _http_get(self, url: str, priority: RequestPriority, **kwargs) -> httpx.Response:
        priority_mgr = get_priority_queue()
        semaphore = await priority_mgr.acquire_slot(priority)
        async with semaphore:
            return await self._client.get(url, **kwargs)
    
    async def get_artist_image(self, artist_id: str, size: Optional[int] = None) -> Optional[tuple[bytes, str, str]]:
        try:
            artist_id = validate_mbid(artist_id, "artist")
        except ValueError as e:
            logger.warning(f"Invalid artist MBID: {e}")
            return None
        
        size_suffix = f"_{size}" if size else ""
        cache_filename = _get_cache_filename(f"artist_{artist_id}{size_suffix}", "img")
        file_path = self.cache_dir / f"{cache_filename}.bin"
        
        if cached := await self._read_disk_cache(file_path, ["wikidata_id"]):
            logger.debug(f"Cache HIT (disk): Artist image {artist_id[:8]}...")
            return cached
        
        if size and size != 250:
            fallback_filename = _get_cache_filename(f"artist_{artist_id}_250", "img")
            fallback_path = self.cache_dir / f"{fallback_filename}.bin"
            if cached := await self._read_disk_cache(fallback_path, ["wikidata_id"]):
                logger.debug(f"Cache HIT (disk - fallback 250px): Artist image {artist_id[:8]}...")
                return cached
        
        logger.debug(f"Cache MISS (disk): Artist image {artist_id[:8]}... - fetching from Wikidata")
        
        dedupe_key = f"artist:img:{artist_id}:{size}"
        return await _deduplicator.dedupe(
            dedupe_key,
            lambda: self._fetch_artist_image(artist_id, size, file_path)
        )
    
    async def _fetch_artist_image(
        self,
        artist_id: str,
        size: Optional[int],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        logger.info(f"[IMG] Fetching artist image for {artist_id[:8]}... (size={size})")
        
        result = await self._fetch_artist_image_from_lidarr(artist_id, size, file_path)
        if result:
            logger.info(f"[IMG] SUCCESS from Lidarr for {artist_id[:8]}...")
            return result
        
        logger.info(f"[IMG] Lidarr failed for {artist_id[:8]}..., trying Wikidata")
        result = await self._fetch_artist_image_from_wikidata(artist_id, size, file_path)
        if result:
            logger.info(f"[IMG] SUCCESS from Wikidata for {artist_id[:8]}...")
            return result
        
        logger.info(f"[IMG] FAILED: No image found for {artist_id[:8]}... from any source")
        return None

    async def _fetch_artist_image_from_lidarr(
        self,
        artist_id: str,
        size: Optional[int],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        if not self._lidarr_repo:
            logger.debug(f"[IMG:Lidarr] No Lidarr repo configured for {artist_id[:8]}")
            return None

        try:
            image_url = await self._lidarr_repo.get_artist_image_url(artist_id, size=size or 250)
            if not image_url:
                logger.info(f"[IMG:Lidarr] No image URL returned for {artist_id[:8]}")
                return None

            logger.info(f"[IMG:Lidarr] Fetching from URL for {artist_id[:8]}...")
            response = await self._http_get(image_url, RequestPriority.IMAGE_FETCH)
            if response.status_code != 200:
                logger.warning(f"[IMG:Lidarr] HTTP {response.status_code} for {artist_id[:8]}")
                return None

            content_type = response.headers.get("content-type", "")
            if not _is_valid_image_content_type(content_type):
                logger.warning(f"[IMG:Lidarr] Non-image content-type ({content_type}) for {artist_id[:8]}")
                return None
            
            content = response.content

            asyncio.create_task(self._write_disk_cache(
                file_path,
                content,
                content_type,
                {"source": "lidarr"}
            ))

            return (content, content_type, "lidarr")

        except Exception as e:
            logger.warning(f"[IMG:Lidarr] Exception for {artist_id[:8]}: {e}")
            return None

    async def _fetch_artist_image_from_wikidata(
        self,
        artist_id: str,
        size: Optional[int],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        cache_key = f"artist_wikidata:{artist_id}"
        wikidata_url = await self._cache.get(cache_key)
        
        if wikidata_url is None:
            logger.info(f"[IMG:Wikidata] Looking up wikidata URL for {artist_id[:8]}...")
            try:
                if self._mb_repo:
                    artist_data = await self._mb_repo.get_artist_by_id(artist_id)
                    
                    if artist_data:
                        url_relations = artist_data.get("url-relation-list") or artist_data.get("url-rels")
                        logger.debug(f"[IMG:Wikidata] url-rels for {artist_id[:8]}: {bool(url_relations)}")
                        if url_relations:
                            for url_rel in url_relations:
                                if isinstance(url_rel, dict):
                                    typ = url_rel.get("type") or url_rel.get("link_type")
                                    target = url_rel.get("target") or url_rel.get("url")
                                    if typ == "wikidata" and target:
                                        wikidata_url = target
                                        logger.info(f"[IMG:Wikidata] Found URL for {artist_id[:8]}: {target}")
                                        break

                        if not wikidata_url:
                            external_links = artist_data.get("external_links") or artist_data.get("external_links_list")
                            if external_links:
                                for ext in external_links:
                                    try:
                                        ext_type = getattr(ext, "type", None) if not isinstance(ext, dict) else ext.get("type")
                                        ext_url = getattr(ext, "url", None) if not isinstance(ext, dict) else ext.get("url")
                                    except Exception:
                                        ext_type = None
                                        ext_url = None

                                    if ext_type == "wikidata" and ext_url:
                                        wikidata_url = ext_url
                                        break
                    else:
                        logger.info(f"[IMG:Wikidata] No artist data from MB for {artist_id[:8]}")
                    
                    ttl = 86400 if wikidata_url else 3600
                    await self._cache.set(cache_key, wikidata_url, ttl_seconds=ttl)
                    if not wikidata_url:
                        logger.info(f"[IMG:Wikidata] No wikidata link found for {artist_id[:8]}")
                else:
                    logger.warning(f"[IMG:Wikidata] MusicBrainz repository not available for {artist_id}")
                    return None
            
            except Exception as e:
                logger.error(f"[IMG:Wikidata] Failed to fetch artist metadata for {artist_id}: {e}")
                return None
        else:
            logger.debug(f"[IMG:Wikidata] Using cached wikidata URL for {artist_id[:8]}")
        
        if not wikidata_url:
            return None

        try:
            match = re.search(r'/(?:wiki|entity)/(Q\d+)', wikidata_url)
            wikidata_id = match.group(1) if match else None
            if not wikidata_id:
                logger.debug(f"Could not parse Wikidata Q-id from URL: {wikidata_url}")
                return None

            api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await self._http_get(api_url, RequestPriority.IMAGE_FETCH)
            if response.status_code != 200:
                return None

            data = response.json()
            entity = data.get("entities", {}).get(wikidata_id, {})
            claims = entity.get("claims", {})
            image_claims = claims.get("P18", [])
            if not image_claims:
                return None

            filename = image_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
            if not filename:
                return None

            commons_api = (
                f"https://commons.wikimedia.org/w/api.php"
                f"?action=query&titles=File:{quote(filename)}"
                f"&prop=imageinfo&iiprop=url&format=json"
            )
            if size:
                commons_api += f"&iiurlwidth={size}"

            commons_response = await self._http_get(commons_api, RequestPriority.IMAGE_FETCH)
            if commons_response.status_code != 200:
                return None

            commons_data = commons_response.json()
            pages = commons_data.get("query", {}).get("pages", {})

            image_url = None
            for page in pages.values():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    if size and "thumburl" in imageinfo[0]:
                        image_url = imageinfo[0].get("thumburl")
                    else:
                        image_url = imageinfo[0].get("url")
                    break

            if not image_url:
                return None

            response = await self._http_get(image_url, RequestPriority.IMAGE_FETCH)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"[IMG:Wikidata] Non-image content-type ({content_type})")
                    return None
                content = response.content

                asyncio.create_task(self._write_disk_cache(
                    file_path,
                    content,
                    content_type,
                    {"wikidata_id": wikidata_id}
                ))

                return (content, content_type, wikidata_id)

        except Exception as e:
            logger.error(f"Error fetching artist image for {artist_id}: {e}")

        return None
    
    async def get_release_group_cover(
        self,
        release_group_id: str,
        size: Optional[str] = "500"
    ) -> Optional[tuple[bytes, str]]:
        try:
            release_group_id = validate_mbid(release_group_id, "release-group")
        except ValueError as e:
            logger.warning(f"Invalid release-group MBID: {e}")
            return None
        
        cache_filename = _get_cache_filename(f"rg_{release_group_id}", size or 'orig')
        file_path = self.cache_dir / f"{cache_filename}.bin"
        
        if cached := await self._read_disk_cache(file_path):
            logger.debug(f"Cache HIT (disk): Album cover {release_group_id[:8]}...")
            return cached
        
        logger.debug(f"Cache MISS (disk): Album cover {release_group_id[:8]}... - fetching from CoverArtArchive")
        
        dedupe_key = f"cover:rg:{release_group_id}:{size}"
        return await _deduplicator.dedupe(
            dedupe_key,
            lambda: self._fetch_release_group_cover(release_group_id, size, file_path)
        )
    
    async def _fetch_release_group_cover(
        self,
        release_group_id: str,
        size: Optional[str],
        file_path: Path
    ) -> Optional[tuple[bytes, str]]:
        size_int = int(size) if size and size.isdigit() else 500
        result = await self._fetch_album_cover_from_lidarr(release_group_id, file_path, size=size_int)
        if result:
            return result

        size_suffix = f"-{size}" if size else ""
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front{size_suffix}"
        
        try:
            response = await self._http_get(front_url, RequestPriority.IMAGE_FETCH)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Non-image content-type from CoverArtArchive: {content_type}")
                else:
                    content = response.content
                    asyncio.create_task(self._write_disk_cache(file_path, content, content_type))
                    return (content, content_type)
        
        except Exception as e:
            logger.debug(f"Failed to fetch cover via release group: {e}")
        
        return await self._get_cover_from_best_release(release_group_id, size, file_path)
    
    async def _get_cover_from_best_release(
        self,
        release_group_id: str,
        size: Optional[str],
        cache_path: Path,
    ) -> Optional[tuple[bytes, str]]:
        try:
            metadata_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}"
            response = await self._http_get(metadata_url, RequestPriority.IMAGE_FETCH, headers={"Accept": "application/json"})
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            release_url = data.get("release", "")
            if not release_url:
                return None
            
            release_id = release_url.split("/")[-1]
            
            try:
                release_id = validate_mbid(release_id, "release")
            except ValueError as e:
                logger.warning(f"Invalid release MBID extracted from metadata: {e}")
                return None
            
            size_suffix = f"-{size}" if size else ""
            release_front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
            
            response = await self._http_get(release_front_url, RequestPriority.IMAGE_FETCH)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Non-image content-type from release: {content_type}")
                    return None
                content = response.content
                
                asyncio.create_task(self._write_disk_cache(cache_path, content, content_type))
                return (content, content_type)
        
        except Exception as e:
            logger.warning(f"Failed to fetch cover from best release: {e}")
        
        return None

    async def _fetch_album_cover_from_lidarr(
        self,
        release_group_id: str,
        file_path: Path,
        size: Optional[int] = 500
    ) -> Optional[tuple[bytes, str]]:
        if not self._lidarr_repo:
            return None

        try:
            image_url = await self._lidarr_repo.get_album_image_url(release_group_id, size=size)
            if not image_url:
                return None

            logger.debug(f"Fetching album cover from Lidarr: {release_group_id[:8]}...")
            response = await self._http_get(image_url, RequestPriority.IMAGE_FETCH)
            if response.status_code != 200:
                return None

            content_type = response.headers.get("content-type", "")
            if not _is_valid_image_content_type(content_type):
                logger.warning(f"Non-image content-type from Lidarr album: {content_type}")
                return None
            
            content = response.content

            asyncio.create_task(self._write_disk_cache(
                file_path,
                content,
                content_type,
                {"source": "lidarr"}
            ))

            return (content, content_type)

        except Exception as e:
            logger.debug(f"Failed to fetch album cover from Lidarr for {release_group_id}: {e}")
            return None

    async def get_release_cover(
        self,
        release_id: str,
        size: Optional[str] = "500"
    ) -> Optional[tuple[bytes, str]]:
        try:
            release_id = validate_mbid(release_id, "release")
        except ValueError as e:
            logger.warning(f"Invalid release MBID: {e}")
            return None
        
        cache_filename = _get_cache_filename(f"rel_{release_id}", size or 'orig')
        file_path = self.cache_dir / f"{cache_filename}.bin"
        
        if cached := await self._read_disk_cache(file_path):
            return cached
        
        size_suffix = f"-{size}" if size else ""
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
        
        try:
            response = await self._http_get(front_url, RequestPriority.IMAGE_FETCH)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Non-image content-type from release cover: {content_type}")
                    return None
                content = response.content
                
                asyncio.create_task(self._write_disk_cache(file_path, content, content_type))
                return (content, content_type)
        
        except Exception as e:
            logger.warning(f"Failed to fetch release cover: {e}")
        
        return None
    
    async def batch_prefetch_covers(
        self,
        album_ids: list[str],
        size: str = "250",
        max_concurrent: int = 10
    ) -> None:
        if not album_ids:
            return
        
        from infrastructure.validators import is_valid_mbid
        valid_album_ids = [aid for aid in album_ids if is_valid_mbid(aid)]
        invalid_count = len(album_ids) - len(valid_album_ids)
        
        if not valid_album_ids:
            logger.warning("No valid MBIDs in batch prefetch request")
            return
        
        if invalid_count > 0:
            invalid_rate = (invalid_count / len(album_ids)) * 100
            logger.warning(f"Filtered out {invalid_count} invalid MBIDs from batch prefetch ({invalid_rate:.1f}%)")
            
            if invalid_rate > 10.0:
                logger.error(
                    f"HIGH INVALID MBID RATE: {invalid_count}/{len(album_ids)} "
                    f"({invalid_rate:.1f}%) - This indicates a potential upstream bug!"
                )
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_limit(album_id: str):
            async with semaphore:
                try:
                    await self.get_release_group_cover(album_id, size)
                except Exception as e:
                    error_msg = str(e)
                    if "Invalid" in error_msg or "MBID" in error_msg:
                        logger.warning(f"Invalid MBID in batch prefetch: {album_id} - {e}")
                    else:
                        logger.debug(f"Failed to prefetch cover for {album_id}: {e}")
        
        logger.info(f"Batch prefetching {len(valid_album_ids)} covers with max {max_concurrent} concurrent requests")
        await asyncio.gather(*[fetch_with_limit(aid) for aid in valid_album_ids], return_exceptions=True)
        logger.debug(f"Completed batch prefetch of {len(valid_album_ids)} covers")
    
    async def promote_cover_to_persistent(self, identifier: str, identifier_type: str = "album") -> bool:
        import json
        from datetime import datetime
        
        if identifier_type == "album":
            cache_filename = _get_cache_filename(identifier, "cover")
        elif identifier_type == "artist":
            cache_filename = _get_cache_filename(f"artist_{identifier}", "img")
        else:
            logger.error(f"Unknown identifier type: {identifier_type}")
            return False
        
        file_path = self.cache_dir / f"{cache_filename}.bin"
        meta_path = Path(f"{file_path}.meta")
        
        if not file_path.exists():
            logger.debug(f"Cover {identifier[:8]}... not found in cache")
            return False
        
        if not meta_path.exists():
            logger.debug(f"Cover {identifier[:8]}... has no metadata file")
            return False
        
        try:
            async with aiofiles.open(meta_path, 'r') as f:
                meta = json.loads(await f.read())
            
            if meta.get('is_monitored') and 'expires_at' not in meta:
                logger.debug(f"Cover {identifier[:8]}... already persistent")
                return False
            
            meta['is_monitored'] = True
            if 'expires_at' in meta:
                del meta['expires_at']
            meta['last_accessed'] = datetime.now().timestamp()
            
            async with aiofiles.open(meta_path, 'w') as f:
                await f.write(json.dumps(meta))
            
            logger.info(f"Promoted cover {identifier[:8]}... to persistent cache")
            return True
        
        except Exception as e:
            logger.error(f"Failed to promote cover {identifier} to persistent: {e}")
            return False

    async def debug_artist_image(self, artist_id: str, debug_info: dict) -> dict:
        """
        Debug method that gathers diagnostic info about an artist image without actually fetching it.
        Returns the updated debug_info dict with cache state, Lidarr data, and MusicBrainz relations.
        """
        import json
        
        cache_filename_250 = _get_cache_filename(f"artist_{artist_id}_250", "img")
        cache_filename_500 = _get_cache_filename(f"artist_{artist_id}_500", "img")
        file_path_250 = self.cache_dir / f"{cache_filename_250}.bin"
        file_path_500 = self.cache_dir / f"{cache_filename_500}.bin"
        
        debug_info["disk_cache"]["exists_250"] = file_path_250.exists()
        debug_info["disk_cache"]["exists_500"] = file_path_500.exists()
        
        if file_path_250.exists():
            meta_path = Path(f"{file_path_250}.meta")
            if meta_path.exists():
                try:
                    async with aiofiles.open(meta_path, 'r') as f:
                        meta = json.loads(await f.read())
                        debug_info["disk_cache"]["meta_250"] = meta
                except Exception as e:
                    debug_info["disk_cache"]["meta_250"] = f"Error reading: {e}"
        
        if file_path_500.exists():
            meta_path = Path(f"{file_path_500}.meta")
            if meta_path.exists():
                try:
                    async with aiofiles.open(meta_path, 'r') as f:
                        meta = json.loads(await f.read())
                        debug_info["disk_cache"]["meta_500"] = meta
                except Exception as e:
                    debug_info["disk_cache"]["meta_500"] = f"Error reading: {e}"
        
        if self._lidarr_repo:
            debug_info["lidarr"]["configured"] = True
            try:
                image_url = await self._lidarr_repo.get_artist_image_url(artist_id)
                if image_url:
                    debug_info["lidarr"]["has_image_url"] = True
                    debug_info["lidarr"]["image_url"] = image_url
            except Exception as e:
                debug_info["lidarr"]["error"] = str(e)
        
        cache_key = f"artist_wikidata:{artist_id}"
        cached_wikidata = await self._cache.get(cache_key)
        if cached_wikidata is not None:
            debug_info["memory_cache"]["wikidata_url_cached"] = True
            debug_info["memory_cache"]["cached_value"] = cached_wikidata if cached_wikidata else "(negative cache - empty string)"
        
        if self._mb_repo and not cached_wikidata:
            try:
                artist_data = await self._mb_repo.get_artist_by_id(artist_id)
                if artist_data:
                    debug_info["musicbrainz"]["artist_found"] = True
                    debug_info["musicbrainz"]["artist_name"] = artist_data.get("name")
                    
                    url_relations = artist_data.get("url-relation-list") or artist_data.get("url-rels")
                    if url_relations:
                        for url_rel in url_relations:
                            if isinstance(url_rel, dict):
                                typ = url_rel.get("type") or url_rel.get("link_type")
                                target = url_rel.get("target") or url_rel.get("url")
                                if typ == "wikidata" and target:
                                    debug_info["musicbrainz"]["has_wikidata_relation"] = True
                                    debug_info["musicbrainz"]["wikidata_url"] = target
                                    break
            except Exception as e:
                debug_info["musicbrainz"]["error"] = str(e)
        elif cached_wikidata:
            debug_info["musicbrainz"]["has_wikidata_relation"] = True
            debug_info["musicbrainz"]["wikidata_url"] = cached_wikidata
        
        return debug_info





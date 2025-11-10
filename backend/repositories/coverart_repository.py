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

if TYPE_CHECKING:
    from repositories.musicbrainz_repository import MusicBrainzRepository

logger = logging.getLogger(__name__)

COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"
DEFAULT_CACHE_DIR = Path("/app/cache/covers")

_coverart_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="coverart"
)


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
        cache_dir: Path = DEFAULT_CACHE_DIR
    ):
        self._client = http_client
        self._cache = cache
        self._mb_repo = mb_repo
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
            
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            
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
            
            async with aiofiles.open(f"{file_path}.meta", "w") as m:
                await m.write(json.dumps(meta))
            
            if extra_meta and 'wikidata_id' in extra_meta:
                async with aiofiles.open(f"{file_path}.wikidata_id", "w") as wf:
                    await wf.write(extra_meta['wikidata_id'])
        
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
            
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            
            meta_file = Path(f"{file_path}.meta")
            if not meta_file.exists():
                return None
            
            async with aiofiles.open(meta_file, "r") as m:
                meta_content = await m.read()
            
            try:
                meta = json.loads(meta_content)
                content_type = meta.get('content_type', 'image/jpeg')
                
                expires_at = meta.get('expires_at')
                if expires_at and datetime.now().timestamp() > expires_at:
                    return None
                
                meta['last_accessed'] = datetime.now().timestamp()
                async with aiofiles.open(meta_file, "w") as m:
                    await m.write(json.dumps(meta))
                    
            except (json.JSONDecodeError, ValueError):
                content_type = meta_content.strip()
            
            result = [content, content_type]
            
            if extra_keys:
                for key in extra_keys:
                    try:
                        async with aiofiles.open(f"{file_path}.{key}", "r") as meta_file:
                            result.append((await meta_file.read()).strip())
                    except FileNotFoundError:
                        result.append(None)
            
            return tuple(result)
        
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Disk cache read error: {e}")
            return None
    
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
        
        cache_key = f"artist_wikidata:{artist_id}"
        wikidata_url = await self._cache.get(cache_key)
        
        if wikidata_url is None:
            try:
                if self._mb_repo:
                    artist_data = await self._mb_repo.get_artist_by_id(artist_id)
                    
                    if artist_data:
                        url_relations = artist_data.get("url-relation-list") or artist_data.get("url-rels")
                        if url_relations:
                            for url_rel in url_relations:
                                if isinstance(url_rel, dict):
                                    typ = url_rel.get("type") or url_rel.get("link_type")
                                    target = url_rel.get("target") or url_rel.get("url")
                                    if typ == "wikidata" and target:
                                        wikidata_url = target
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
                    
                    ttl = 86400 if wikidata_url else 3600
                    await self._cache.set(cache_key, wikidata_url, ttl_seconds=ttl)
                else:
                    logger.warning(f"MusicBrainz repository not available for artist {artist_id}")
                    return None
            
            except Exception as e:
                logger.error(f"Failed to fetch artist metadata for {artist_id}: {e}")
                return None
        
        if not wikidata_url:
            return None

        try:
            match = re.search(r'/(?:wiki|entity)/(Q\d+)', wikidata_url)
            wikidata_id = match.group(1) if match else None
            if not wikidata_id:
                logger.debug(f"Could not parse Wikidata Q-id from URL: {wikidata_url}")
                return None

            api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await self._http_get(api_url, RequestPriority.USER_INITIATED)
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

            commons_response = await self._http_get(commons_api, RequestPriority.USER_INITIATED)
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

            response = await self._http_get(image_url, RequestPriority.USER_INITIATED)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
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
        
        size_suffix = f"-{size}" if size else ""
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front{size_suffix}"
        
        try:
            response = await self._http_get(front_url, RequestPriority.USER_INITIATED)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
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
            response = await self._http_get(metadata_url, RequestPriority.USER_INITIATED, headers={"Accept": "application/json"})
            
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
            
            response = await self._http_get(release_front_url, RequestPriority.USER_INITIATED)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
                content = response.content
                
                asyncio.create_task(self._write_disk_cache(cache_path, content, content_type))
                return (content, content_type)
        
        except Exception as e:
            logger.warning(f"Failed to fetch cover from best release: {e}")
        
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
            response = await self._http_get(front_url, RequestPriority.USER_INITIATED)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
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





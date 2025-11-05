"""Cover Art Archive repository for fetching album covers and artist images."""
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

if TYPE_CHECKING:
    from repositories.musicbrainz_repository import MusicBrainzRepository

logger = logging.getLogger(__name__)

COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"
CACHE_DIR = Path("/app/cache/covers")

CACHE_DIR.mkdir(parents=True, exist_ok=True)

_coverart_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="coverart"
)


def _get_cache_filename(identifier: str, suffix: str = "") -> str:
    """Generate cache filename using SHA1 hash to avoid path length issues.
    
    Args:
        identifier: Unique identifier (e.g., artist_id, release_id)
        suffix: Optional suffix to add before extension
    
    Returns:
        SHA1 hash-based filename
    """
    content = f"{identifier}:{suffix}"
    hash_digest = hashlib.sha1(content.encode()).hexdigest()
    return hash_digest


class CoverArtRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
        mb_repo: Optional['MusicBrainzRepository'] = None
    ):
        self._client = http_client
        self._cache = cache
        self._mb_repo = mb_repo
    
    async def _write_disk_cache(
        self,
        file_path: Path,
        content: bytes,
        content_type: str,
        extra_meta: Optional[dict[str, str]] = None,
    ) -> None:
        """Write content to disk cache with metadata."""
        try:
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            
            async with aiofiles.open(f"{file_path}.meta", "w") as m:
                await m.write(content_type)
            
            if extra_meta:
                for key, value in extra_meta.items():
                    async with aiofiles.open(f"{file_path}.{key}", "w") as meta_file:
                        await meta_file.write(value)
        
        except Exception as e:
            logger.warning(f"Failed to write disk cache: {e}")
    
    async def _read_disk_cache(
        self,
        file_path: Path,
        extra_keys: Optional[list[str]] = None,
    ) -> Optional[tuple]:
        """Read content from disk cache."""
        try:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            
            async with aiofiles.open(f"{file_path}.meta", "r") as m:
                content_type = (await m.read()).strip()
            
            result = [content, content_type]
            
            if extra_keys:
                for key in extra_keys:
                    async with aiofiles.open(f"{file_path}.{key}", "r") as meta_file:
                        result.append((await meta_file.read()).strip())
            
            return tuple(result)
        
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Disk cache read error: {e}")
            return None
    
    @with_retry(max_attempts=3, circuit_breaker=_coverart_circuit_breaker)
    async def _http_get(self, url: str, **kwargs) -> httpx.Response:
        """Make HTTP GET request with retry and circuit breaker."""
        return await self._client.get(url, **kwargs)
    
    async def get_artist_image(self, artist_id: str) -> Optional[tuple[bytes, str, str]]:
        """Get artist image from Wikidata.
        
        Args:
            artist_id: MusicBrainz artist ID
        
        Returns:
            Tuple of (image_data, content_type, wikidata_id) or None
        """
        cache_filename = _get_cache_filename(f"artist_{artist_id}", "img")
        file_path = CACHE_DIR / f"{cache_filename}.bin"
        
        if cached := await self._read_disk_cache(file_path, ["wikidata_id"]):
            return cached
        
        cache_key = f"artist_wikidata:{artist_id}"
        wikidata_url = await self._cache.get(cache_key)
        
        if wikidata_url is None:
            try:
                if self._mb_repo:
                    artist_data = await self._mb_repo.get_artist_by_id(artist_id)
                    
                    if artist_data:
                        url_relations = artist_data.get("url-relation-list", [])
                        for url_rel in url_relations:
                            if url_rel.get("type") == "wikidata":
                                wikidata_url = url_rel.get("target")
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
            match = re.search(r'/wiki/(Q\d+)', wikidata_url)
            wikidata_id = match.group(1) if match else None
            if not wikidata_id:
                return None
            
            try:
                api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
                response = await self._http_get(api_url)
                
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
                
                commons_response = await self._http_get(commons_api)
                if commons_response.status_code != 200:
                    return None
                
                commons_data = commons_response.json()
                pages = commons_data.get("query", {}).get("pages", {})
                
                image_url = None
                for page in pages.values():
                    imageinfo = page.get("imageinfo", [])
                    if imageinfo:
                        image_url = imageinfo[0].get("url")
                        break
                
                if not image_url:
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching Wikidata image for {wikidata_id}: {e}")
                return None
            
            response = await self._http_get(image_url)
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
        """Get cover art for a release group.
        
        Args:
            release_group_id: MusicBrainz release group ID
            size: Image size ("250", "500", "1200", or None for original)
        
        Returns:
            Tuple of (image_data, content_type) or None
        """
        cache_filename = _get_cache_filename(f"rg_{release_group_id}", size or 'orig')
        file_path = CACHE_DIR / f"{cache_filename}.bin"
        
        if cached := await self._read_disk_cache(file_path):
            return cached
        
        size_suffix = f"-{size}" if size else ""
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front{size_suffix}"
        
        try:
            response = await self._http_get(front_url)
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
        """Fallback: get cover art from best release in group."""
        try:
            metadata_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}"
            response = await self._http_get(metadata_url, headers={"Accept": "application/json"})
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            release_url = data.get("release", "")
            if not release_url:
                return None
            
            release_id = release_url.split("/")[-1]
            
            size_suffix = f"-{size}" if size else ""
            release_front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
            
            response = await self._http_get(release_front_url)
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
        """Get cover art for a specific release.
        
        Args:
            release_id: MusicBrainz release ID
            size: Image size ("250", "500", "1200", or None for original)
        
        Returns:
            Tuple of (image_data, content_type) or None
        """
        cache_filename = _get_cache_filename(f"rel_{release_id}", size or 'orig')
        file_path = CACHE_DIR / f"{cache_filename}.bin"
        
        if cached := await self._read_disk_cache(file_path):
            return cached
        
        size_suffix = f"-{size}" if size else ""
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
        
        try:
            response = await self._http_get(front_url)
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
        """Batch prefetch covers with concurrency control to avoid N+1 queries.
        
        Args:
            album_ids: List of MusicBrainz release group IDs
            size: Image size to fetch
            max_concurrent: Maximum number of concurrent requests
        """
        if not album_ids:
            return
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_limit(album_id: str):
            async with semaphore:
                try:
                    await self.get_release_group_cover(album_id, size)
                except Exception as e:
                    logger.debug(f"Failed to prefetch cover for {album_id}: {e}")
        
        logger.info(f"Batch prefetching {len(album_ids)} covers with max {max_concurrent} concurrent requests")
        await asyncio.gather(*[fetch_with_limit(aid) for aid in album_ids], return_exceptions=True)
        logger.debug(f"Completed batch prefetch of {len(album_ids)} covers")



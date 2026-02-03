import asyncio
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import aiofiles
import httpx

from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from infrastructure.validators import validate_mbid
from infrastructure.queue.priority_queue import RequestPriority, get_priority_queue
from infrastructure.http.deduplication import RequestDeduplicator
from repositories.coverart_artist import ArtistImageFetcher
from repositories.coverart_album import AlbumCoverFetcher
from repositories.coverart_disk_cache import CoverDiskCache, get_cache_filename

if TYPE_CHECKING:
    from repositories.musicbrainz_repository import MusicBrainzRepository
    from repositories.lidarr import LidarrRepository

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
        self._disk_cache = CoverDiskCache(cache_dir)
        self._artist_fetcher = ArtistImageFetcher(
            http_get_fn=self._http_get,
            write_cache_fn=self._disk_cache.write,
            cache=cache,
            mb_repo=mb_repo,
            lidarr_repo=lidarr_repo
        )
        self._album_fetcher = AlbumCoverFetcher(
            http_get_fn=self._http_get,
            write_cache_fn=self._disk_cache.write,
            lidarr_repo=lidarr_repo
        )
    
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
        file_path = self._disk_cache.get_file_path(f"artist_{artist_id}{size_suffix}", "img")

        if cached := await self._disk_cache.read(file_path, ["wikidata_id"]):
            logger.debug(f"Cache HIT (disk): Artist image {artist_id[:8]}...")
            return cached

        if size and size != 250:
            fallback_path = self._disk_cache.get_file_path(f"artist_{artist_id}_250", "img")
            if cached := await self._disk_cache.read(fallback_path, ["wikidata_id"]):
                logger.debug(f"Cache HIT (disk - fallback 250px): Artist image {artist_id[:8]}...")
                return cached

        logger.debug(f"Cache MISS (disk): Artist image {artist_id[:8]}... - fetching from Wikidata")

        dedupe_key = f"artist:img:{artist_id}:{size}"
        return await _deduplicator.dedupe(
            dedupe_key,
            lambda: self._artist_fetcher.fetch_artist_image(artist_id, size, file_path)
        )

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

        file_path = self._disk_cache.get_file_path(f"rg_{release_group_id}", size or 'orig')

        if cached := await self._disk_cache.read(file_path):
            logger.debug(f"Cache HIT (disk): Album cover {release_group_id[:8]}...")
            return (cached[0], cached[1])

        logger.debug(f"Cache MISS (disk): Album cover {release_group_id[:8]}... - fetching from CoverArtArchive")

        dedupe_key = f"cover:rg:{release_group_id}:{size}"
        return await _deduplicator.dedupe(
            dedupe_key,
            lambda: self._album_fetcher.fetch_release_group_cover(release_group_id, size, file_path)
        )

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

        file_path = self._disk_cache.get_file_path(f"rel_{release_id}", size or 'orig')

        if cached := await self._disk_cache.read(file_path):
            return (cached[0], cached[1])

        dedupe_key = f"cover:rel:{release_id}:{size}"
        return await _deduplicator.dedupe(
            dedupe_key,
            lambda: self._album_fetcher.fetch_release_cover(release_id, size, file_path)
        )
    
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
        return await self._disk_cache.promote_to_persistent(identifier, identifier_type)

    async def debug_artist_image(self, artist_id: str, debug_info: dict) -> dict:
        import json

        file_path_250 = self._disk_cache.get_file_path(f"artist_{artist_id}_250", "img")
        file_path_500 = self._disk_cache.get_file_path(f"artist_{artist_id}_500", "img")

        debug_info["disk_cache"]["exists_250"] = file_path_250.exists()
        debug_info["disk_cache"]["exists_500"] = file_path_500.exists()

        for size, file_path in [("250", file_path_250), ("500", file_path_500)]:
            if file_path.exists():
                meta_path = file_path.with_suffix('.meta.json')
                if meta_path.exists():
                    try:
                        async with aiofiles.open(meta_path, 'r') as f:
                            debug_info["disk_cache"][f"meta_{size}"] = json.loads(await f.read())
                    except Exception as e:
                        debug_info["disk_cache"][f"meta_{size}"] = f"Error reading: {e}"

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
            debug_info["memory_cache"]["cached_value"] = cached_wikidata if cached_wikidata else "(negative cache)"

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

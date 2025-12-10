import logging
import asyncio
from typing import Any, TYPE_CHECKING
from repositories.lidarr_repository import LidarrRepository
from repositories.coverart_repository import CoverArtRepository, _get_cache_filename, DEFAULT_CACHE_DIR
from api.v1.schemas.library import LibraryAlbum, LibraryArtist, LibraryStatsResponse
from infrastructure.cache.persistent_cache import LibraryCache
from core.exceptions import ExternalServiceError
from services.cache_status_service import CacheStatusService

if TYPE_CHECKING:
    from services.preferences_service import PreferencesService
    from services.artist_service import ArtistService
    from services.album_service import AlbumService

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(
        self, 
        lidarr_repo: LidarrRepository, 
        library_cache: LibraryCache,
        cover_repo: CoverArtRepository,
        preferences_service: 'PreferencesService'
    ):
        self._lidarr_repo = lidarr_repo
        self._library_cache = library_cache
        self._cover_repo = cover_repo
        self._preferences_service = preferences_service
        self._last_sync_time: float = 0.0
        self._last_manual_sync: float = 0.0
        self._manual_sync_cooldown: float = 60.0
        self._global_sync_cooldown: float = 30.0
        self._sync_lock = asyncio.Lock()
    
    async def get_library(self) -> list[LibraryAlbum]:
        try:
            albums_data = await self._library_cache.get_albums()
            
            if not albums_data:
                logger.info("Library cache is empty, syncing from Lidarr")
                await self.sync_library()
                albums_data = await self._library_cache.get_albums()
            
            albums = [
                LibraryAlbum(
                    artist=album['artist_name'],
                    album=album['title'],
                    year=album.get('year'),
                    monitored=bool(album.get('monitored', 1)),
                    quality=None,
                    cover_url=album.get('cover_url'),
                    musicbrainz_id=album.get('mbid'),
                    artist_mbid=album.get('artist_mbid'),
                    date_added=album.get('date_added')
                )
                for album in albums_data
            ]
            
            return albums
        except Exception as e:
            logger.error(f"Failed to fetch library: {e}")
            raise ExternalServiceError(f"Failed to fetch library: {e}")
    
    async def get_library_mbids(self) -> list[str]:
        try:
            mbids_set = await self._lidarr_repo.get_library_mbids(include_release_ids=False)
            return list(mbids_set)
        except Exception as e:
            logger.error(f"Failed to fetch library mbids: {e}")
            raise ExternalServiceError(f"Failed to fetch library mbids: {e}")
    
    async def get_artists(self, limit: int | None = None) -> list[LibraryArtist]:
        try:
            artists_data = await self._library_cache.get_artists(limit=limit)
            
            if not artists_data:
                logger.info("Artists cache is empty, syncing from Lidarr")
                await self.sync_library()
                artists_data = await self._library_cache.get_artists(limit=limit)
            
            artists = [
                LibraryArtist(
                    mbid=artist['mbid'],
                    name=artist['name'],
                    album_count=artist.get('album_count', 0),
                    date_added=artist.get('date_added')
                )
                for artist in artists_data
            ]
            
            return artists
        except Exception as e:
            logger.error(f"Failed to fetch artists: {e}")
            raise ExternalServiceError(f"Failed to fetch artists: {e}")
    
    async def get_recently_added(self, limit: int = 20) -> list[LibraryAlbum]:

        try:
            albums = await self._lidarr_repo.get_recently_imported(limit=limit)
            
            if not albums:
                logger.info("No recent imports from history, falling back to cache")
                albums_data = await self._library_cache.get_recently_added(limit=limit)
                
                albums = [
                    LibraryAlbum(
                        artist=album['artist_name'],
                        album=album['title'],
                        year=album.get('year'),
                        monitored=bool(album.get('monitored', 1)),
                        quality=None,
                        cover_url=album.get('cover_url'),
                        musicbrainz_id=album.get('mbid'),
                        artist_mbid=album.get('artist_mbid'),
                        date_added=album.get('date_added')
                    )
                    for album in albums_data
                ]
            
            return albums
        except Exception as e:
            logger.error(f"Failed to fetch recently added: {e}")
            raise ExternalServiceError(f"Failed to fetch recently added: {e}")
    
    async def sync_library(self, is_manual: bool = False) -> dict:
        from services.cache_status_service import CacheStatusService
        import time
        
        try:
            status_service = CacheStatusService()
            
            async with self._sync_lock:
                current_time = time.time()
                
                time_since_last_sync = current_time - self._last_sync_time
                if time_since_last_sync < self._global_sync_cooldown:
                    remaining = int(self._global_sync_cooldown - time_since_last_sync)
                    logger.info(f"Global sync cooldown active ({remaining}s remaining). Skipping sync.")
                    raise ExternalServiceError(
                        f"Sync cooldown active. Please wait {remaining} seconds before syncing again."
                    )
                
                if is_manual:
                    time_since_last_manual = current_time - self._last_manual_sync
                    if time_since_last_manual < self._manual_sync_cooldown:
                        remaining = int(self._manual_sync_cooldown - time_since_last_manual)
                        raise ExternalServiceError(
                            f"Manual sync cooldown active. Please wait {remaining} seconds before syncing again."
                        )
                
                if status_service.is_syncing():
                    logger.warning("Library sync already in progress - cancelling previous sync to start fresh")
                    await status_service.cancel_current_sync()
                    await status_service.wait_for_completion()
                
                self._last_sync_time = current_time
                if is_manual:
                    self._last_manual_sync = current_time
            
            logger.info("Starting library sync from Lidarr")
            
            albums = await self._lidarr_repo.get_library()
            artists = await self._lidarr_repo.get_artists_from_library()
            
            albums_data = [
                {
                    'mbid': album.musicbrainz_id or f"unknown_{album.album}",
                    'artist_mbid': album.artist_mbid,
                    'artist_name': album.artist,
                    'title': album.album,
                    'year': album.year,
                    'cover_url': album.cover_url,
                    'monitored': album.monitored,
                    'date_added': album.date_added
                }
                for album in albums
            ]
            
            await self._library_cache.save_library(artists, albums_data)
            logger.info("Library cache updated - unmonitored items removed")
            
            task = asyncio.create_task(self._precache_library_resources(artists, albums))
            status_service.set_current_task(task)
            
            logger.info(f"Library sync complete: {len(artists)} artists, {len(albums)} albums")
            
            return {
                'status': 'success',
                'artists': len(artists),
                'albums': len(albums)
            }
        except Exception as e:
            logger.error(f"Failed to sync library: {e}")
            raise ExternalServiceError(f"Failed to sync library: {e}")
        finally:
            if 'status_service' in locals():
                status_service.set_current_task(None)
    
    async def _precache_library_resources(self, artists: list[dict], albums: list[Any]) -> None:
        status_service = CacheStatusService()
        task = None
        
        try:
            task = asyncio.create_task(
                self._do_precache_library_resources(artists, albums, status_service)
            )
            await asyncio.wait_for(task, timeout=1800.0)
        except asyncio.TimeoutError:
            logger.error("Library pre-cache operation timed out after 30 minutes")
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Pre-cache task successfully cancelled after timeout")
                except Exception as e:
                    logger.error(f"Error during task cancellation: {e}")
            await status_service.complete_sync()
            raise ExternalServiceError("Library sync timed out - too many items or slow network")
        except asyncio.CancelledError:
            logger.warning("Pre-cache was cancelled")
            await status_service.complete_sync()
            raise
    
    async def _do_precache_library_resources(self, artists: list[dict], albums: list[Any], status_service: CacheStatusService) -> None:
        from core.dependencies import get_album_service
        
        try:
            logger.info(f"Starting pre-cache for {len(artists)} monitored artists and {len(albums)} monitored albums")
            
            logger.info("Pre-fetching Lidarr library data...")
            album_service = get_album_service()
            library_artist_mbids = await self._lidarr_repo.get_artist_mbids()
            library_album_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
            logger.info(f"Lidarr data cached: {len(library_artist_mbids)} artists, {len(library_album_mbids)} albums")
            
            logger.info(f"Phase 1: Caching {len(artists)} artist metadata + images")
            await status_service.start_sync('artists', len(artists))
            await self._precache_artist_images(artists, status_service, library_artist_mbids, library_album_mbids)

            if status_service.is_cancelled():
                logger.info("Pre-cache cancelled after Phase 1")
                return


            from infrastructure.validators import is_unknown_mbid
            monitored_mbids: set[str] = set()
            for a in albums:
                mbid = getattr(a, 'musicbrainz_id', None) if hasattr(a, 'musicbrainz_id') else a.get('mbid') if isinstance(a, dict) else None
                if not is_unknown_mbid(mbid):
                    monitored_mbids.add(mbid.lower())

            logger.info(f"Phase 2: Collecting {len(monitored_mbids)} monitored album MBIDs (unmonitored albums will NOT be pre-cached)")
            
            deduped_release_groups = list(monitored_mbids)

            if status_service.is_cancelled():
                logger.info("Pre-cache cancelled after Phase 2")
                return

            logger.info(f"Phase 3: Batch-checking which of {len(deduped_release_groups)} release-groups need caching...")
            
            items_needing_metadata = []
            cache_checks = []
            
            for rgid in deduped_release_groups:
                cache_key = f"album_info:{rgid}"
                cache_checks.append((rgid, album_service._cache.get(cache_key)))
            
            cache_results = await asyncio.gather(*[check for _, check in cache_checks])
            
            for (rgid, _), cached_info in zip(cache_checks, cache_results):
                if not cached_info:
                    items_needing_metadata.append(rgid)
            
            items_needing_covers = []
            cover_paths = []
            
            for rgid in deduped_release_groups:
                if rgid.lower() in monitored_mbids:
                    cache_filename = _get_cache_filename(f"rg_{rgid}", "500")
                    file_path = DEFAULT_CACHE_DIR / f"{cache_filename}.bin"
                    cover_paths.append((rgid, file_path))
            
            for rgid, file_path in cover_paths:
                if not file_path.exists():
                    items_needing_covers.append(rgid)
            
            items_to_process = list(set(items_needing_metadata + items_needing_covers))
            
            already_cached = len(deduped_release_groups) - len(items_to_process)
            logger.info(
                f"Phase 3: {len(items_to_process)} items need caching "
                f"({len(items_needing_metadata)} metadata, {len(items_needing_covers)} covers) - "
                f"{already_cached} already cached, skipping"
            )
            
            if items_to_process:
                await status_service.start_sync('albums', len(items_to_process))
                await self._precache_album_data(items_to_process, monitored_mbids, status_service, library_album_mbids)
            else:
                logger.info("All release-groups already cached, nothing to fetch!")
            
            logger.info("Library resource pre-caching complete")
        
        except Exception as e:
            logger.error(f"Error during pre-cache: {e}")
            raise
        finally:
            if status_service.is_syncing():
                await status_service.complete_sync()
    
    async def _precache_artist_images(
        self, 
        artists: list[dict], 
        status_service: CacheStatusService,
        library_artist_mbids: set[str] = None,
        library_album_mbids: dict[str, Any] = None
    ) -> None:
        logger.info(f"Pre-caching metadata+images for {len(artists)} artists")

        from core.dependencies import get_artist_service
        from infrastructure.validators import is_unknown_mbid
        artist_service = get_artist_service()

        async def cache_artist(artist: dict, index: int) -> None:
            try:
                mbid = artist.get('mbid')
                artist_name = artist.get('name', 'Unknown')

                if is_unknown_mbid(mbid):
                    await status_service.update_progress(index + 1, artist_name)
                    return

                artist_cache_key = f"artist_info:{mbid}"
                cached_artist = await artist_service._cache.get(artist_cache_key)
                
                if not cached_artist:
                    try:
                        await artist_service.get_artist_info(
                            mbid,
                            library_artist_mbids=library_artist_mbids,
                            library_album_mbids=library_album_mbids
                        )
                    except Exception:
                        logger.debug(f"Failed to cache artist metadata for {artist_name}")
                else:
                    logger.debug(f"Artist metadata for {artist_name} already cached, skipping fetch")

                cache_filename_250 = _get_cache_filename(f"artist_{mbid}_250", "img")
                file_path_250 = DEFAULT_CACHE_DIR / f"{cache_filename_250}.bin"
                cache_filename_500 = _get_cache_filename(f"artist_{mbid}_500", "img")
                file_path_500 = DEFAULT_CACHE_DIR / f"{cache_filename_500}.bin"

                if file_path_250.exists() and file_path_500.exists():
                    logger.debug(f"Artist images for {artist_name} already cached, skipping")
                    await status_service.update_progress(index + 1, artist_name)
                    return

                await status_service.update_progress(index + 1, f"Fetching images for {artist_name}")
                if not file_path_250.exists():
                    await self._cover_repo.get_artist_image(mbid, size=250)
                if not file_path_500.exists():
                    await self._cover_repo.get_artist_image(mbid, size=500)
                await status_service.update_progress(index + 1, artist_name)

            except Exception as e:
                logger.warning(f"Failed to cache artist {artist.get('name')} (mbid: {mbid}): {e}", exc_info=True)
                await status_service.update_progress(index + 1, f"Failed: {artist.get('name', 'Unknown')}")

        advanced_settings = self._preferences_service.get_advanced_settings()
        batch_size = advanced_settings.batch_artist_images
        for i in range(0, len(artists), batch_size):
            if status_service.is_cancelled():
                logger.info("Artist pre-caching cancelled by user")
                break
                
            batch = artists[i:i + batch_size]
            tasks = [cache_artist(artist, i + idx) for idx, artist in enumerate(batch)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    artist_name = batch[idx].get('name', 'Unknown')
                    logger.error(f"Batch error caching artist {artist_name}: {result}")
            
            await asyncio.sleep(advanced_settings.delay_artist)

        logger.info("Artist metadata+image pre-caching complete")
    
    async def _precache_album_data(
        self, 
        release_group_ids: list[str], 
        monitored_mbids: set[str], 
        status_service: CacheStatusService,
        library_album_mbids: dict[str, Any] = None
    ) -> None:
        from core.dependencies import get_album_service

        logger.info(f"Pre-caching {len(release_group_ids)} new/missing release-groups")

        album_service = get_album_service()

        async def cache_rg(rgid: str, index: int) -> tuple[bool, bool]:
            try:
                if not rgid or rgid.startswith('unknown_'):
                    return (False, False)

                metadata_fetched = False
                cover_fetched = False

                cache_key = f"album_info:{rgid}"
                cached_info = await album_service._cache.get(cache_key)

                if not cached_info:
                    await status_service.update_progress(index + 1, f"Fetching metadata for {rgid[:8]}...")
                    await album_service.get_album_info(rgid, monitored_mbids=monitored_mbids)
                    metadata_fetched = True
                else:
                    await status_service.update_progress(index + 1, f"Cached: {rgid[:8]}...")

                if rgid.lower() in monitored_mbids:
                    cache_filename = _get_cache_filename(f"rg_{rgid}", "500")
                    file_path = DEFAULT_CACHE_DIR / f"{cache_filename}.bin"
                    if not file_path.exists():
                        try:
                            await self._cover_repo.get_cover_image(rgid, size=500)
                            cover_fetched = True
                        except Exception as e:
                            logger.debug(f"Failed to cache cover for {rgid}: {e}")

                return (metadata_fetched, cover_fetched)

            except Exception as e:
                logger.debug(f"Failed to pre-cache release-group {rgid}: {e}")
                return (False, False)

        advanced_settings = self._preferences_service.get_advanced_settings()
        batch_size = advanced_settings.batch_albums
        min_batch = max(1, advanced_settings.batch_albums - 2)
        max_batch = min(20, advanced_settings.batch_albums + 7)
        metadata_fetched = 0
        covers_fetched = 0
        consecutive_slow_batches = 0
        
        import time as time_module

        for i in range(0, len(release_group_ids), batch_size):
            if status_service.is_cancelled():
                logger.info("Album pre-caching cancelled by user")
                break
                
            batch_start = time_module.time()
            
            batch = release_group_ids[i:i + batch_size]
            tasks = [cache_rg(rg, i + idx) for idx, rg in enumerate(batch)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in enumerate(results):
                if isinstance(result, tuple):
                    if result[0]:
                        metadata_fetched += 1
                    if result[1]:
                        covers_fetched += 1
                elif isinstance(result, Exception):
                    rgid = batch[idx] if idx < len(batch) else 'Unknown'
                    logger.error(f"Batch error caching album {rgid[:8] if isinstance(rgid, str) else rgid}: {result}")
            
            batch_duration = time_module.time() - batch_start
            avg_time_per_item = batch_duration / len(batch) if batch else 1.0
            
            if avg_time_per_item > 1.5:
                consecutive_slow_batches += 1
                if consecutive_slow_batches >= 3:
                    batch_size = max(batch_size - 2, min_batch)
                    logger.warning(f"Sustained slowness detected, reducing batch size to {batch_size}")
                elif batch_size > min_batch:
                    batch_size = max(batch_size - 1, min_batch)
                    logger.debug(f"Decreasing batch size to {batch_size} (slow: {avg_time_per_item:.2f}s/item)")
            else:
                consecutive_slow_batches = 0
                if avg_time_per_item < 0.8 and batch_size < max_batch:
                    batch_size = min(batch_size + 1, max_batch)
                    logger.debug(f"Increasing batch size to {batch_size} (fast: {avg_time_per_item:.2f}s/item)")

            if (i + batch_size) % 30 == 0 or (i + batch_size) >= len(release_group_ids):
                percent = int((min(i + batch_size, len(release_group_ids)) / len(release_group_ids)) * 100)
                logger.info(f"Album progress: {min(i + batch_size, len(release_group_ids))}/{len(release_group_ids)} ({percent}%) - metadata: {metadata_fetched}, covers: {covers_fetched} [batch: {batch_size}]")

            await asyncio.sleep(advanced_settings.delay_albums)

        logger.info(
            f"Album pre-caching complete: metadata fetched={metadata_fetched}, covers fetched={covers_fetched}, total processed={len(release_group_ids)}"
        )
    
    async def get_stats(self) -> LibraryStatsResponse:
        try:
            stats = await self._library_cache.get_stats()
            
            return LibraryStatsResponse(
                artist_count=stats['artist_count'],
                album_count=stats['album_count'],
                last_sync=stats['last_sync'],
                db_size_bytes=stats['db_size_bytes'],
                db_size_mb=round(stats['db_size_bytes'] / (1024 * 1024), 2)
            )
        except Exception as e:
            logger.error(f"Failed to fetch library stats: {e}")
            raise ExternalServiceError(f"Failed to fetch library stats: {e}")
    
    async def clear_cache(self) -> None:
        try:
            await self._library_cache.clear()
            logger.info("Library cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear library cache: {e}")
            raise ExternalServiceError(f"Failed to clear library cache: {e}")
    
    async def get_library_grouped(self) -> list[dict[str, Any]]:
        try:
            return await self._lidarr_repo.get_library_grouped()
        except Exception as e:
            logger.error(f"Failed to fetch grouped library: {e}")
            raise ExternalServiceError(f"Failed to fetch grouped library: {e}")

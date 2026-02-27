import logging
import asyncio
import time
from typing import Any
from repositories.protocols import LidarrRepositoryProtocol, CoverArtRepositoryProtocol
from repositories.coverart_repository import DEFAULT_CACHE_DIR
from repositories.coverart_disk_cache import get_cache_filename
from services.cache_status_service import CacheStatusService
from core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class LibraryPrecacheService:
    def __init__(
        self,
        lidarr_repo: LidarrRepositoryProtocol,
        cover_repo: CoverArtRepositoryProtocol,
        preferences_service: Any,
        library_cache: Any,
        artist_discovery_service: Any = None,
    ):
        self._lidarr_repo = lidarr_repo
        self._cover_repo = cover_repo
        self._preferences_service = preferences_service
        self._library_cache = library_cache
        self._artist_discovery_service = artist_discovery_service

    async def precache_library_resources(self, artists: list[dict], albums: list[Any], resume: bool = False) -> None:
        status_service = CacheStatusService(self._library_cache)
        task = None
        try:
            task = asyncio.create_task(self._do_precache(artists, albums, status_service, resume))
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
            await status_service.complete_sync("Sync timed out after 30 minutes")
            raise ExternalServiceError("Library sync timed out - too many items or slow network")
        except asyncio.CancelledError:
            logger.warning("Pre-cache was cancelled")
            await status_service.complete_sync()
            raise
        except Exception as e:
            logger.error(f"Pre-cache failed: {e}")
            await status_service.complete_sync(str(e))
            raise

    async def _do_precache(self, artists: list[dict], albums: list[Any], status_service: CacheStatusService, resume: bool = False) -> None:
        from core.dependencies import get_album_service
        try:
            processed_artists: set[str] = set()
            processed_albums: set[str] = set()
            skip_artists = False

            if resume:
                logger.info("Resuming interrupted sync...")
                processed_artists = await self._library_cache.get_processed_items('artist')
                processed_albums = await self._library_cache.get_processed_items('album')

                state = await self._library_cache.get_sync_state()
                if state and state.get('phase') == 'albums':
                    skip_artists = True
                    logger.info(f"Resuming from albums phase, {len(processed_albums)} albums already processed")
                else:
                    logger.info(f"Resuming from artists phase, {len(processed_artists)} artists already processed")

            total_artists = len(artists)
            total_albums = len(albums)

            logger.info(f"Starting pre-cache for {total_artists} monitored artists and {total_albums} monitored albums")
            logger.info("Pre-fetching Lidarr library data...")
            album_service = get_album_service()
            library_artist_mbids = await self._lidarr_repo.get_artist_mbids()
            library_album_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
            logger.info(f"Lidarr data cached: {len(library_artist_mbids)} artists, {len(library_album_mbids)} albums")

            if not skip_artists:
                remaining_artists = [a for a in artists if a.get('mbid') not in processed_artists]
                logger.info(f"Phase 1: Caching {len(remaining_artists)} artist metadata + images ({len(processed_artists)} already done)")
                await status_service.start_sync('artists', len(remaining_artists), total_artists=total_artists, total_albums=total_albums)
                await self._precache_artist_images(remaining_artists, status_service, library_artist_mbids, library_album_mbids, len(processed_artists))
            if status_service.is_cancelled():
                logger.info("Pre-cache cancelled after Phase 1")
                return

            if self._artist_discovery_service and not skip_artists:
                artist_mbids = [
                    a.get('mbid') for a in artists
                    if a.get('mbid') and not a.get('mbid', '').startswith('unknown_')
                ]
                if artist_mbids:
                    logger.info(f"Phase 1.5: Pre-caching discovery data (popular albums/songs/similar) for {len(artist_mbids)} library artists")
                    try:
                        advanced_settings = self._preferences_service.get_advanced_settings()
                        precache_delay = advanced_settings.artist_discovery_precache_delay
                        await self._artist_discovery_service.precache_artist_discovery(
                            artist_mbids, delay=precache_delay
                        )
                    except Exception as e:
                        logger.warning(f"Discovery precache failed (non-fatal): {e}")

            if status_service.is_cancelled():
                logger.info("Pre-cache cancelled after Phase 1.5")
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
                if rgid in processed_albums:
                    continue
                cache_key = f"album_info:{rgid}"
                cache_checks.append((rgid, album_service._cache.get(cache_key)))
            cache_results = await asyncio.gather(*[check for _, check in cache_checks])
            for (rgid, _), cached_info in zip(cache_checks, cache_results):
                if not cached_info:
                    items_needing_metadata.append(rgid)
            items_needing_covers = []
            cover_paths = []
            for rgid in deduped_release_groups:
                if rgid in processed_albums:
                    continue
                if rgid.lower() in monitored_mbids:
                    cache_filename = get_cache_filename(f"rg_{rgid}", "500")
                    file_path = DEFAULT_CACHE_DIR / f"{cache_filename}.bin"
                    cover_paths.append((rgid, file_path))
            for rgid, file_path in cover_paths:
                if not file_path.exists():
                    items_needing_covers.append(rgid)
            items_to_process = list(set(items_needing_metadata + items_needing_covers))
            already_cached = len(deduped_release_groups) - len(items_to_process) - len(processed_albums)
            logger.info(
                f"Phase 3: {len(items_to_process)} items need caching "
                f"({len(items_needing_metadata)} metadata, {len(items_needing_covers)} covers) - "
                f"{already_cached} already cached, {len(processed_albums)} from previous run"
            )
            if items_to_process:
                await status_service.update_phase('albums', len(items_to_process))
                await self._precache_album_data(items_to_process, monitored_mbids, status_service, library_album_mbids, len(processed_albums))
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
        library_album_mbids: dict[str, Any] = None,
        offset: int = 0
    ) -> None:
        logger.info(f"Pre-caching metadata+images for {len(artists)} artists")
        from core.dependencies import get_artist_service
        from infrastructure.validators import is_unknown_mbid
        artist_service = get_artist_service()

        async def cache_artist(artist: dict, index: int) -> str:
            mbid = artist.get('mbid')
            try:
                artist_name = artist.get('name', 'Unknown')
                if is_unknown_mbid(mbid):
                    await status_service.update_progress(index + 1, artist_name, processed_artists=offset + index + 1)
                    return mbid
                artist_cache_key = f"artist_info:{mbid}"
                cached_artist = await artist_service._cache.get(artist_cache_key)
                if not cached_artist:
                    try:
                        await artist_service.get_artist_info(mbid, library_artist_mbids, library_album_mbids)
                    except Exception:
                        logger.debug(f"Failed to cache artist metadata for {artist_name}")
                else:
                    logger.debug(f"Artist metadata for {artist_name} already cached, skipping fetch")
                cache_filename_250 = get_cache_filename(f"artist_{mbid}_250", "img")
                file_path_250 = DEFAULT_CACHE_DIR / f"{cache_filename_250}.bin"
                cache_filename_500 = get_cache_filename(f"artist_{mbid}_500", "img")
                file_path_500 = DEFAULT_CACHE_DIR / f"{cache_filename_500}.bin"
                if file_path_250.exists() and file_path_500.exists():
                    logger.debug(f"Artist images for {artist_name} already cached, skipping")
                    await status_service.update_progress(index + 1, artist_name, processed_artists=offset + index + 1)
                    return mbid
                await status_service.update_progress(index + 1, f"Fetching images for {artist_name}", processed_artists=offset + index + 1)
                if not file_path_250.exists():
                    await self._cover_repo.get_artist_image(mbid, size=250)
                if not file_path_500.exists():
                    await self._cover_repo.get_artist_image(mbid, size=500)
                await status_service.update_progress(index + 1, artist_name, processed_artists=offset + index + 1)
                return mbid
            except Exception as e:
                logger.warning(f"Failed to cache artist {artist.get('name')} (mbid: {mbid}): {e}", exc_info=True)
                await status_service.update_progress(index + 1, f"Failed: {artist.get('name', 'Unknown')}", processed_artists=offset + index + 1)
                return mbid

        advanced_settings = self._preferences_service.get_advanced_settings()
        batch_size = advanced_settings.batch_artist_images
        for i in range(0, len(artists), batch_size):
            if status_service.is_cancelled():
                logger.info("Artist pre-caching cancelled by user")
                break
            batch = artists[i:i + batch_size]
            tasks = [cache_artist(artist, i + idx) for idx, artist in enumerate(batch)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            processed_mbids = []
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    artist_name = batch[idx].get('name', 'Unknown')
                    logger.error(f"Batch error caching artist {artist_name}: {result}")
                    processed_mbids.append(batch[idx].get('mbid'))
                elif result:
                    processed_mbids.append(result)
            if processed_mbids:
                await self._library_cache.mark_items_processed_batch('artist', processed_mbids)
            await status_service.persist_progress()
            await asyncio.sleep(advanced_settings.delay_artist)
        logger.info("Artist metadata+image pre-caching complete")
        await self._cache_artist_genres(artists)

    async def _cache_artist_genres(self, artists: list[dict]) -> None:
        from core.dependencies import get_artist_service
        artist_service = get_artist_service()
        artist_genres: dict[str, list[str]] = {}
        logger.info(f"Extracting genre tags for {len(artists)} library artists")
        for artist in artists:
            mbid = artist.get('mbid')
            if not mbid:
                continue
            cache_key = f"artist_info:{mbid}"
            cached_info = await artist_service._cache.get(cache_key)
            if cached_info and hasattr(cached_info, 'tags') and cached_info.tags:
                artist_genres[mbid] = cached_info.tags[:10]
        if artist_genres:
            await self._library_cache.save_artist_genres(artist_genres)
            logger.info(f"Cached genres for {len(artist_genres)} artists")
        else:
            logger.info("No artist genres found to cache")

    async def _precache_album_data(
        self,
        release_group_ids: list[str],
        monitored_mbids: set[str],
        status_service: CacheStatusService,
        library_album_mbids: dict[str, Any] = None,
        offset: int = 0
    ) -> None:
        from core.dependencies import get_album_service
        logger.info(f"Pre-caching {len(release_group_ids)} new/missing release-groups")
        album_service = get_album_service()

        async def cache_rg(rgid: str, index: int) -> tuple[str, bool, bool]:
            try:
                if not rgid or rgid.startswith('unknown_'):
                    return (rgid, False, False)
                metadata_fetched = False
                cover_fetched = False
                cache_key = f"album_info:{rgid}"
                cached_info = await album_service._cache.get(cache_key)
                if not cached_info:
                    await status_service.update_progress(index + 1, f"Fetching metadata for {rgid[:8]}...", processed_albums=offset + index + 1)
                    await album_service.get_album_info(rgid, monitored_mbids=monitored_mbids)
                    metadata_fetched = True
                else:
                    await status_service.update_progress(index + 1, f"Cached: {rgid[:8]}...", processed_albums=offset + index + 1)
                if rgid.lower() in monitored_mbids:
                    cache_filename = get_cache_filename(f"rg_{rgid}", "500")
                    file_path = DEFAULT_CACHE_DIR / f"{cache_filename}.bin"
                    if not file_path.exists():
                        try:
                            await self._cover_repo.get_cover_image(rgid, size=500)
                            cover_fetched = True
                        except Exception as e:
                            logger.debug(f"Failed to cache cover for {rgid}: {e}")
                return (rgid, metadata_fetched, cover_fetched)
            except Exception as e:
                logger.debug(f"Failed to pre-cache release-group {rgid}: {e}")
                return (rgid, False, False)

        advanced_settings = self._preferences_service.get_advanced_settings()
        batch_size = advanced_settings.batch_albums
        min_batch = max(1, advanced_settings.batch_albums - 2)
        max_batch = min(20, advanced_settings.batch_albums + 7)
        metadata_fetched = 0
        covers_fetched = 0
        consecutive_slow_batches = 0
        for i in range(0, len(release_group_ids), batch_size):
            if status_service.is_cancelled():
                logger.info("Album pre-caching cancelled by user")
                break
            batch_start = time.time()
            batch = release_group_ids[i:i + batch_size]
            tasks = [cache_rg(rg, i + idx) for idx, rg in enumerate(batch)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            processed_mbids = []
            for idx, result in enumerate(results):
                if isinstance(result, tuple) and len(result) == 3:
                    rgid, meta, cover = result
                    if meta:
                        metadata_fetched += 1
                    if cover:
                        covers_fetched += 1
                    if rgid:
                        processed_mbids.append(rgid)
                elif isinstance(result, Exception):
                    rgid = batch[idx] if idx < len(batch) else 'Unknown'
                    logger.error(f"Batch error caching album {rgid[:8] if isinstance(rgid, str) else rgid}: {result}")
                    if isinstance(rgid, str):
                        processed_mbids.append(rgid)
            if processed_mbids:
                await self._library_cache.mark_items_processed_batch('album', processed_mbids)
            await status_service.persist_progress()
            batch_duration = time.time() - batch_start
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
        logger.info(f"Album pre-caching complete: metadata fetched={metadata_fetched}, covers fetched={covers_fetched}, total processed={len(release_group_ids)}")

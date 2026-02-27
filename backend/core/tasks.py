import asyncio
import logging
from time import time
from typing import TYPE_CHECKING
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.validators import is_unknown_mbid
from services.library_service import LibraryService
from services.preferences_service import PreferencesService

if TYPE_CHECKING:
    from services.album_service import AlbumService
    from services.home_service import HomeService
    from services.discover_service import DiscoverService
    from services.discover_queue_manager import DiscoverQueueManager
    from services.artist_discovery_service import ArtistDiscoveryService
    from infrastructure.cache.persistent_cache import LibraryCache

logger = logging.getLogger(__name__)


async def cleanup_cache_periodically(cache: CacheInterface, interval: int = 300) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            await cache.cleanup_expired()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cache cleanup task: {e}")


def start_cache_cleanup_task(cache: CacheInterface, interval: int = 300) -> asyncio.Task:
    return asyncio.create_task(cleanup_cache_periodically(cache, interval=interval))


async def cleanup_disk_cache_periodically(disk_cache: DiskMetadataCache, interval: int = 600) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            logger.debug("Running disk cache cleanup...")
            await disk_cache.cleanup_expired_recent()
            await disk_cache.enforce_recent_size_limits()
            await disk_cache.cleanup_expired_covers()
            await disk_cache.enforce_cover_size_limits()
            logger.debug("Disk cache cleanup complete")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in disk cache cleanup task: {e}")


def start_disk_cache_cleanup_task(disk_cache: DiskMetadataCache, interval: int = 600) -> asyncio.Task:
    return asyncio.create_task(cleanup_disk_cache_periodically(disk_cache, interval=interval))


async def sync_library_periodically(
    library_service: LibraryService,
    preferences_service: PreferencesService
) -> None:
    while True:
        try:
            lidarr_settings = preferences_service.get_lidarr_settings()
            sync_freq = lidarr_settings.sync_frequency
            
            if sync_freq == "manual":
                await asyncio.sleep(3600)
                continue
            elif sync_freq == "5min":
                interval = 300
            elif sync_freq == "10min":
                interval = 600
            elif sync_freq == "30min":
                interval = 1800
            elif sync_freq == "1hr":
                interval = 3600
            else:
                interval = 600
            
            await asyncio.sleep(interval)
            
            logger.info(f"Auto-syncing library (frequency: {sync_freq})")
            sync_success = False
            try:
                await library_service.sync_library()
                sync_success = True
                logger.info("Auto-sync completed successfully")
                
            except Exception as e:
                logger.error(f"Failed to auto-sync library: {e}")
                sync_success = False
            
            finally:
                lidarr_settings = preferences_service.get_lidarr_settings()
                updated_settings = lidarr_settings.model_copy(update={
                    'last_sync': int(time()),
                    'last_sync_success': sync_success
                })
                preferences_service.save_lidarr_settings(updated_settings)
        
        except asyncio.CancelledError:
            logger.info("Library sync task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in library sync task: {e}")
            await asyncio.sleep(60)


def start_library_sync_task(
    library_service: LibraryService,
    preferences_service: PreferencesService
) -> asyncio.Task:
    return asyncio.create_task(sync_library_periodically(library_service, preferences_service))


async def warm_library_cache(
    library_service: LibraryService,
    album_service: 'AlbumService',
    library_cache: 'LibraryCache'
) -> None:
    try:
        logger.info("Warming cache with recently-added library albums...")
        
        await asyncio.sleep(5)
        
        albums_data = await library_cache.get_albums()
        
        if not albums_data:
            logger.info("No library albums to warm cache with")
            return

        max_warm = 30
        albums_to_warm = albums_data[:max_warm]
        
        logger.info(f"Warming cache with {len(albums_to_warm)} of {len(albums_data)} library albums (first {max_warm})")
        
        warmed = 0
        for i, album_data in enumerate(albums_to_warm):
            mbid = album_data.get('mbid')
            if mbid and not is_unknown_mbid(mbid):
                try:
                    if not await album_service.is_album_cached(mbid):
                        await album_service.get_album_info(mbid)
                        warmed += 1

                    if i % 5 == 0:
                        await asyncio.sleep(1)

                except Exception as e:
                    logger.debug(f"Failed to warm cache for album {album_data.get('title')}: {e}")
                    continue
        
        logger.info(f"Cache warming complete: {warmed} albums fetched, {len(albums_to_warm) - warmed} already cached")
    
    except Exception as e:
        logger.error(f"Failed to warm library cache: {e}")


async def warm_home_cache_periodically(
    home_service: 'HomeService',
    interval: int = 240
) -> None:
    await asyncio.sleep(10)

    while True:
        try:
            for src in ("listenbrainz", "lastfm"):
                try:
                    logger.debug("Warming home page cache (source=%s)...", src)
                    await home_service.get_home_data(source=src)
                    logger.debug("Home cache warming complete (source=%s)", src)
                except Exception as e:
                    logger.warning("Home cache warming failed (source=%s): %s", src, e)
        except asyncio.CancelledError:
            logger.info("Home cache warming task cancelled")
            break

        await asyncio.sleep(interval)


def start_home_cache_warming_task(home_service: 'HomeService') -> asyncio.Task:
    return asyncio.create_task(warm_home_cache_periodically(home_service))


async def warm_discover_cache_periodically(
    discover_service: 'DiscoverService',
    interval: int = 43200,
    queue_manager: 'DiscoverQueueManager | None' = None,
    preferences_service: 'PreferencesService | None' = None,
) -> None:
    await asyncio.sleep(30)

    while True:
        try:
            for src in ("listenbrainz", "lastfm"):
                try:
                    logger.info("Warming discover cache (source=%s)...", src)
                    await discover_service.warm_cache(source=src)
                    logger.info("Discover cache warming complete (source=%s)", src)
                except Exception as e:
                    logger.warning("Discover cache warming failed (source=%s): %s", src, e)

            if queue_manager and preferences_service:
                try:
                    adv = preferences_service.get_advanced_settings()
                    if adv.discover_queue_auto_generate and adv.discover_queue_warm_cycle_build:
                        resolved = discover_service.resolve_source(None)
                        logger.info("Pre-building discover queue (source=%s)...", resolved)
                        await queue_manager.start_build(resolved)
                except Exception as e:
                    logger.warning("Discover queue pre-build failed: %s", e)

        except asyncio.CancelledError:
            logger.info("Discover cache warming task cancelled")
            break

        await asyncio.sleep(interval)


def start_discover_cache_warming_task(
    discover_service: 'DiscoverService',
    queue_manager: 'DiscoverQueueManager | None' = None,
    preferences_service: 'PreferencesService | None' = None,
) -> asyncio.Task:
    return asyncio.create_task(
        warm_discover_cache_periodically(
            discover_service,
            queue_manager=queue_manager,
            preferences_service=preferences_service,
        )
    )


async def warm_jellyfin_mbid_index(jellyfin_repo: 'JellyfinRepository') -> None:
    from repositories.jellyfin_repository import JellyfinRepository as _JR

    await asyncio.sleep(8)
    try:
        index = await jellyfin_repo.build_mbid_index()
        logger.info("Jellyfin MBID index warmed with %d entries", len(index))
    except Exception as e:
        logger.warning("Jellyfin MBID index warming failed: %s", e)


async def warm_artist_discovery_cache_periodically(
    artist_discovery_service: 'ArtistDiscoveryService',
    library_cache: 'LibraryCache',
    interval: int = 14400,
    delay: float = 0.5,
) -> None:
    await asyncio.sleep(60)

    while True:
        try:
            artists = await library_cache.get_artists()
            if not artists:
                logger.debug("No library artists for discovery cache warming")
                await asyncio.sleep(interval)
                continue

            mbids = [
                a['mbid'] for a in artists
                if a.get('mbid') and not is_unknown_mbid(a['mbid'])
            ]
            if not mbids:
                await asyncio.sleep(interval)
                continue

            logger.info(
                "Warming artist discovery cache for %d library artists...", len(mbids)
            )
            cached = await artist_discovery_service.precache_artist_discovery(
                mbids, delay=delay
            )
            logger.info(
                "Artist discovery cache warming complete: %d/%d artists refreshed",
                cached, len(mbids),
            )
        except asyncio.CancelledError:
            logger.info("Artist discovery cache warming task cancelled")
            break
        except Exception as e:
            logger.warning("Artist discovery cache warming failed: %s", e)

        await asyncio.sleep(interval)


def start_artist_discovery_cache_warming_task(
    artist_discovery_service: 'ArtistDiscoveryService',
    library_cache: 'LibraryCache',
    interval: int = 14400,
    delay: float = 0.5,
) -> asyncio.Task:
    return asyncio.create_task(
        warm_artist_discovery_cache_periodically(
            artist_discovery_service,
            library_cache,
            interval=interval,
            delay=delay,
        )
    )


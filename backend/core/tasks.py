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


def start_cache_cleanup_task(cache: CacheInterface) -> asyncio.Task:
    return asyncio.create_task(cleanup_cache_periodically(cache))


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


def start_disk_cache_cleanup_task(disk_cache: DiskMetadataCache) -> asyncio.Task:
    return asyncio.create_task(cleanup_disk_cache_periodically(disk_cache))


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
            logger.debug("Warming home page cache...")
            await home_service.get_home_data()
            logger.debug("Home cache warming complete")
        except asyncio.CancelledError:
            logger.info("Home cache warming task cancelled")
            break
        except Exception as e:
            logger.warning(f"Home cache warming failed: {e}")
        
        await asyncio.sleep(interval)


def start_home_cache_warming_task(home_service: 'HomeService') -> asyncio.Task:
    return asyncio.create_task(warm_home_cache_periodically(home_service))


async def warm_discover_cache_periodically(
    discover_service: 'DiscoverService',
    interval: int = 43200,
) -> None:
    from services.discover_service import DiscoverService as _DS

    await asyncio.sleep(30)

    while True:
        try:
            logger.info("Warming discover cache...")
            await discover_service.warm_cache()
            logger.info("Discover cache warming complete")
        except asyncio.CancelledError:
            logger.info("Discover cache warming task cancelled")
            break
        except Exception as e:
            logger.warning(f"Discover cache warming failed: {e}")

        await asyncio.sleep(interval)


def start_discover_cache_warming_task(discover_service: 'DiscoverService') -> asyncio.Task:
    return asyncio.create_task(warm_discover_cache_periodically(discover_service))


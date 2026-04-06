import asyncio
import logging
from time import time
from typing import TYPE_CHECKING, Optional
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.serialization import clone_with_updates
from infrastructure.validators import is_unknown_mbid
from services.library_service import LibraryService
from services.preferences_service import PreferencesService
from core.task_registry import TaskRegistry

if TYPE_CHECKING:
    from services.album_service import AlbumService
    from services.audiodb_image_service import AudioDBImageService
    from services.home_service import HomeService
    from services.discover_service import DiscoverService
    from services.discover_queue_manager import DiscoverQueueManager
    from services.artist_discovery_service import ArtistDiscoveryService
    from services.library_precache_service import LibraryPrecacheService
    from infrastructure.persistence import LibraryDB
    from infrastructure.persistence.request_history import RequestHistoryStore
    from infrastructure.persistence.mbid_store import MBIDStore
    from infrastructure.persistence.youtube_store import YouTubeStore
    from services.requests_page_service import RequestsPageService
    from repositories.coverart_disk_cache import CoverDiskCache

logger = logging.getLogger(__name__)


async def cleanup_cache_periodically(cache: CacheInterface, interval: int = 300) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            await cache.cleanup_expired()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Cache cleanup task failed: %s", e, exc_info=True)


def start_cache_cleanup_task(cache: CacheInterface, interval: int = 300) -> asyncio.Task:
    task = asyncio.create_task(cleanup_cache_periodically(cache, interval=interval))
    TaskRegistry.get_instance().register("cache-cleanup", task)
    return task


async def cleanup_disk_cache_periodically(
    disk_cache: DiskMetadataCache,
    interval: int = 600,
    cover_disk_cache: Optional["CoverDiskCache"] = None,
) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            logger.debug("Running disk cache cleanup...")
            await disk_cache.cleanup_expired_recent()
            await disk_cache.enforce_recent_size_limits()
            await disk_cache.cleanup_expired_covers()
            await disk_cache.enforce_cover_size_limits()
            if cover_disk_cache:
                await cover_disk_cache.enforce_size_limit(force=True)
                expired = await asyncio.to_thread(cover_disk_cache.cleanup_expired)
                if expired:
                    logger.info("Cover expiry sweep removed %d expired covers", expired)
            logger.debug("Disk cache cleanup complete")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Disk cache cleanup task failed: %s", e, exc_info=True)


def start_disk_cache_cleanup_task(
    disk_cache: DiskMetadataCache,
    interval: int = 600,
    cover_disk_cache: Optional["CoverDiskCache"] = None,
) -> asyncio.Task:
    task = asyncio.create_task(
        cleanup_disk_cache_periodically(disk_cache, interval=interval, cover_disk_cache=cover_disk_cache)
    )
    TaskRegistry.get_instance().register("disk-cache-cleanup", task)
    return task


async def sync_library_periodically(
    library_service: LibraryService,
    preferences_service: PreferencesService
) -> None:
    while True:
        try:
            if not library_service._lidarr_repo.is_configured():
                await asyncio.sleep(3600)
                continue

            lidarr_settings = preferences_service.get_lidarr_settings()
            sync_freq = lidarr_settings.sync_frequency
            
            if sync_freq == "manual":
                await asyncio.sleep(3600)
                continue
            
            freq_to_seconds = {
                "5min": 300,
                "10min": 600,
                "30min": 1800,
                "1hr": 3600,
                "6hr": 21600,
                "12hr": 43200,
                "24hr": 86400,
                "3d": 259200,
                "7d": 604800,
            }
            interval = freq_to_seconds.get(sync_freq, 86400)
            
            await asyncio.sleep(interval)
            
            logger.info(f"Auto-syncing library (frequency: {sync_freq})")
            sync_success = False
            should_update_status = True
            try:
                result = await library_service.sync_library()
                if result.status == "skipped":
                    logger.info("Auto-sync skipped - sync already in progress")
                    should_update_status = False
                    continue
                sync_success = True
                logger.info("Auto-sync completed successfully")
                
            except Exception as e:
                logger.error("Auto-sync library call failed: %s", e, exc_info=True)
                sync_success = False
            
            finally:
                if should_update_status:
                    lidarr_settings = preferences_service.get_lidarr_settings()
                    updated_settings = clone_with_updates(lidarr_settings, {
                        'last_sync': int(time()),
                        'last_sync_success': sync_success
                    })
                    preferences_service.save_lidarr_settings(updated_settings)
        
        except asyncio.CancelledError:
            logger.info("Library sync task cancelled")
            break
        except Exception as e:
            logger.error("Library sync task failed: %s", e, exc_info=True)
            await asyncio.sleep(60)


def start_library_sync_task(
    library_service: LibraryService,
    preferences_service: PreferencesService
) -> asyncio.Task:
    task = asyncio.create_task(sync_library_periodically(library_service, preferences_service))
    TaskRegistry.get_instance().register("library-sync", task)
    return task


async def warm_library_cache(
    library_service: LibraryService,
    album_service: 'AlbumService',
    library_db: 'LibraryDB'
) -> None:
    try:
        logger.info("Warming cache with recently-added library albums...")
        
        await asyncio.sleep(5)
        
        albums_data = await library_db.get_albums()
        
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
                    logger.error(
                        "Library cache warm item failed album=%s mbid=%s error=%s",
                        album_data.get('title'),
                        mbid,
                        e,
                        exc_info=True,
                    )
                    continue
        
        logger.info(f"Cache warming complete: {warmed} albums fetched, {len(albums_to_warm) - warmed} already cached")
    
    except Exception as e:
        logger.error("Library cache warming failed: %s", e, exc_info=True)


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
                    logger.error(
                        "Home cache warming failed (source=%s): %s",
                        src,
                        e,
                        exc_info=True,
                    )
        except asyncio.CancelledError:
            logger.info("Home cache warming task cancelled")
            break

        await asyncio.sleep(interval)


def start_home_cache_warming_task(home_service: 'HomeService') -> asyncio.Task:
    task = asyncio.create_task(warm_home_cache_periodically(home_service))
    TaskRegistry.get_instance().register("home-cache-warming", task)
    return task


async def warm_genre_cache_periodically(
    home_service: 'HomeService',
    interval: int = 21600,
) -> None:
    from api.v1.schemas.home import HomeGenre

    RETRY_INTERVAL = 60

    await asyncio.sleep(30)

    while True:
        warmed = 0
        try:
            for src in ("listenbrainz", "lastfm"):
                try:
                    cached_home = await home_service.get_cached_home_data(source=src)
                    if not cached_home or not cached_home.genre_list or not cached_home.genre_list.items:
                        logger.debug("No cached home data for genre warming (source=%s), skipping", src)
                        continue
                    genre_names = [
                        g.name for g in cached_home.genre_list.items[:20]
                        if isinstance(g, HomeGenre)
                    ]
                    if genre_names:
                        logger.debug("Warming genre cache (source=%s, %d genres)...", src, len(genre_names))
                        await home_service._genre.build_and_cache_genre_section(src, genre_names)
                        logger.debug("Genre cache warming complete (source=%s)", src)
                        warmed += 1
                except Exception as e:
                    logger.error(
                        "Genre cache warming failed (source=%s): %s",
                        src,
                        e,
                        exc_info=True,
                    )
        except asyncio.CancelledError:
            logger.info("Genre cache warming task cancelled")
            break

        if warmed == 0:
            await asyncio.sleep(RETRY_INTERVAL)
        else:
            try:
                ttl = home_service._genre._get_genre_section_ttl()
            except Exception:  # noqa: BLE001
                ttl = interval
            await asyncio.sleep(ttl)


def start_genre_cache_warming_task(home_service: 'HomeService') -> asyncio.Task:
    task = asyncio.create_task(warm_genre_cache_periodically(home_service))
    TaskRegistry.get_instance().register("genre-cache-warming", task)
    return task


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
                    logger.error(
                        "Discover cache warming failed (source=%s): %s",
                        src,
                        e,
                        exc_info=True,
                    )

            if queue_manager and preferences_service:
                try:
                    adv = preferences_service.get_advanced_settings()
                    if adv.discover_queue_auto_generate and adv.discover_queue_warm_cycle_build:
                        resolved = discover_service.resolve_source(None)
                        logger.info("Pre-building discover queue (source=%s)...", resolved)
                        await queue_manager.start_build(resolved)
                except Exception as e:
                    logger.error("Discover queue pre-build failed: %s", e, exc_info=True)

        except asyncio.CancelledError:
            logger.info("Discover cache warming task cancelled")
            break

        await asyncio.sleep(interval)


def start_discover_cache_warming_task(
    discover_service: 'DiscoverService',
    queue_manager: 'DiscoverQueueManager | None' = None,
    preferences_service: 'PreferencesService | None' = None,
) -> asyncio.Task:
    task = asyncio.create_task(
        warm_discover_cache_periodically(
            discover_service,
            queue_manager=queue_manager,
            preferences_service=preferences_service,
        )
    )
    TaskRegistry.get_instance().register("discover-cache-warming", task)
    return task


async def warm_jellyfin_mbid_index(jellyfin_repo: 'JellyfinRepository') -> None:
    from repositories.jellyfin_repository import JellyfinRepository as _JR

    await asyncio.sleep(8)
    try:
        index = await jellyfin_repo.build_mbid_index()
        logger.info("Jellyfin MBID index warmed with %d entries", len(index))
    except Exception as e:
        logger.error("Jellyfin MBID index warming failed: %s", e, exc_info=True)


async def warm_navidrome_mbid_cache() -> None:
    from core.dependencies import get_navidrome_library_service

    await asyncio.sleep(12)
    while True:
        try:
            service = get_navidrome_library_service()
            await service.warm_mbid_cache()
        except Exception as e:
            logger.error("Navidrome MBID cache warming failed: %s", e, exc_info=True)
        await asyncio.sleep(14400)  # Re-warm every 4 hours


async def warm_artist_discovery_cache_periodically(
    artist_discovery_service: 'ArtistDiscoveryService',
    library_db: 'LibraryDB',
    interval: int = 14400,
    delay: float = 0.5,
) -> None:
    await asyncio.sleep(300)  # Wait for Phase 1.5 sync to finish first

    while True:
        try:
            artists = await library_db.get_artists()
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
            logger.error("Artist discovery cache warming failed: %s", e, exc_info=True)

        await asyncio.sleep(interval)


def start_artist_discovery_cache_warming_task(
    artist_discovery_service: 'ArtistDiscoveryService',
    library_db: 'LibraryDB',
    interval: int = 14400,
    delay: float = 0.5,
) -> asyncio.Task:
    task = asyncio.create_task(
        warm_artist_discovery_cache_periodically(
            artist_discovery_service,
            library_db,
            interval=interval,
            delay=delay,
        )
    )
    TaskRegistry.get_instance().register("artist-discovery-warming", task)
    return task


_AUDIODB_SWEEP_INTERVAL = 86400
_AUDIODB_SWEEP_INITIAL_DELAY = 120
_AUDIODB_SWEEP_MAX_ITEMS = 5000
_AUDIODB_SWEEP_INTER_ITEM_DELAY = 2.0
_AUDIODB_SWEEP_CURSOR_PERSIST_INTERVAL = 50
_AUDIODB_SWEEP_LOG_INTERVAL = 100


async def warm_audiodb_cache_periodically(
    audiodb_image_service: 'AudioDBImageService',
    library_db: 'LibraryDB',
    preferences_service: 'PreferencesService',
    precache_service: 'LibraryPrecacheService | None' = None,
) -> None:
    if precache_service is None:
        logger.warning("AudioDB sweep: precache_service not available, byte downloads disabled")
    await asyncio.sleep(_AUDIODB_SWEEP_INITIAL_DELAY)

    while True:
        try:
            await asyncio.sleep(_AUDIODB_SWEEP_INTERVAL)

            settings = preferences_service.get_advanced_settings()
            if not settings.audiodb_enabled:
                logger.debug("AudioDB sweep skipped (audiodb_enabled=false)")
                continue

            artists = await library_db.get_artists()
            albums = await library_db.get_albums()
            if not artists and not albums:
                logger.debug("AudioDB sweep: no library items")
                continue

            cursor = preferences_service.get_setting('audiodb_sweep_cursor')
            all_items: list[tuple[str, str, dict]] = []

            for a in (artists or []):
                mbid = a.get('mbid')
                if mbid and not is_unknown_mbid(mbid):
                    all_items.append(("artist", mbid, a))
            for a in (albums or []):
                mbid = a.get('mbid') if isinstance(a, dict) else getattr(a, 'musicbrainz_id', None)
                if mbid and not is_unknown_mbid(mbid):
                    all_items.append(("album", mbid, a))

            all_items.sort(key=lambda x: x[1])

            if cursor:
                start_idx = 0
                for i, (_, mbid, _) in enumerate(all_items):
                    if mbid > cursor:
                        start_idx = i
                        break
                else:
                    start_idx = 0
                    cursor = None
                all_items = all_items[start_idx:]

            items_needing_refresh: list[tuple[str, str, dict]] = []
            for entity_type, mbid, data in all_items:
                if len(items_needing_refresh) >= _AUDIODB_SWEEP_MAX_ITEMS:
                    break
                if entity_type == "artist":
                    cached = await audiodb_image_service.get_cached_artist_images(mbid)
                else:
                    cached = await audiodb_image_service.get_cached_album_images(mbid)
                if cached is None:
                    items_needing_refresh.append((entity_type, mbid, data))

            if not items_needing_refresh:
                preferences_service.save_setting('audiodb_sweep_cursor', None)
                preferences_service.save_setting('audiodb_sweep_last_completed', time())
                logger.info("AudioDB sweep complete: all items up to date")
                continue

            logger.info(
                "audiodb.sweep action=start items=%d cursor=%s",
                len(items_needing_refresh), cursor[:8] if cursor else 'start',
            )

            processed = 0
            bytes_ok = 0
            bytes_fail = 0
            for entity_type, mbid, data in items_needing_refresh:
                if not preferences_service.get_advanced_settings().audiodb_enabled:
                    logger.info("AudioDB disabled during sweep, stopping")
                    break

                try:
                    if entity_type == "artist":
                        name = data.get('name') if isinstance(data, dict) else None
                        result = await audiodb_image_service.fetch_and_cache_artist_images(
                            mbid, name, is_monitored=True,
                        )
                        if result and not result.is_negative and result.thumb_url and precache_service:
                            if await precache_service._download_audiodb_bytes(result.thumb_url, "artist", mbid):
                                bytes_ok += 1
                            else:
                                bytes_fail += 1
                    else:
                        artist_name = data.get('artist_name') if isinstance(data, dict) else getattr(data, 'artist_name', None)
                        album_name = data.get('title') if isinstance(data, dict) else getattr(data, 'title', None)
                        result = await audiodb_image_service.fetch_and_cache_album_images(
                            mbid, artist_name=artist_name,
                            album_name=album_name, is_monitored=True,
                        )
                        if result and not result.is_negative and result.album_thumb_url and precache_service:
                            if await precache_service._download_audiodb_bytes(result.album_thumb_url, "album", mbid):
                                bytes_ok += 1
                            else:
                                bytes_fail += 1
                except Exception as e:
                    logger.error(
                        "audiodb.sweep action=item_error entity_type=%s mbid=%s error=%s",
                        entity_type,
                        mbid[:8],
                        e,
                        exc_info=True,
                    )

                processed += 1
                if processed % _AUDIODB_SWEEP_CURSOR_PERSIST_INTERVAL == 0:
                    preferences_service.save_setting('audiodb_sweep_cursor', mbid)

                if processed % _AUDIODB_SWEEP_LOG_INTERVAL == 0:
                    logger.info(
                        "audiodb.sweep processed=%d total=%d cursor=%s bytes_ok=%d bytes_fail=%d remaining=%d",
                        processed, len(items_needing_refresh), mbid[:8],
                        bytes_ok, bytes_fail, len(items_needing_refresh) - processed,
                    )

                await asyncio.sleep(_AUDIODB_SWEEP_INTER_ITEM_DELAY)

            if processed >= len(items_needing_refresh):
                preferences_service.save_setting('audiodb_sweep_cursor', None)
                preferences_service.save_setting('audiodb_sweep_last_completed', time())
                logger.info(
                    "audiodb.sweep action=complete refreshed=%d bytes_ok=%d bytes_fail=%d",
                    processed, bytes_ok, bytes_fail,
                )
            else:
                preferences_service.save_setting('audiodb_sweep_cursor', mbid)
                logger.info(
                    "audiodb.sweep action=interrupted processed=%d total=%d bytes_ok=%d bytes_fail=%d",
                    processed, len(items_needing_refresh), bytes_ok, bytes_fail,
                )

        except asyncio.CancelledError:
            logger.info("AudioDB sweep task cancelled")
            break
        except Exception as e:
            logger.error("AudioDB sweep cycle failed: %s", e, exc_info=True)


def start_audiodb_sweep_task(
    audiodb_image_service: 'AudioDBImageService',
    library_db: 'LibraryDB',
    preferences_service: 'PreferencesService',
    precache_service: 'LibraryPrecacheService | None' = None,
) -> asyncio.Task:
    task = asyncio.create_task(
        warm_audiodb_cache_periodically(
            audiodb_image_service, library_db, preferences_service,
            precache_service=precache_service,
        )
    )
    TaskRegistry.get_instance().register("audiodb-sweep", task)
    return task


_REQUEST_SYNC_INTERVAL = 60
_REQUEST_SYNC_INITIAL_DELAY = 15


async def sync_request_statuses_periodically(
    requests_page_service: 'RequestsPageService',
    interval: int = _REQUEST_SYNC_INTERVAL,
) -> None:
    await asyncio.sleep(_REQUEST_SYNC_INITIAL_DELAY)

    while True:
        try:
            await requests_page_service.sync_request_statuses()
        except asyncio.CancelledError:
            logger.info("Request status sync task cancelled")
            break
        except Exception as e:
            logger.error("Periodic request status sync failed: %s", e, exc_info=True)

        await asyncio.sleep(interval)


def start_request_status_sync_task(
    requests_page_service: 'RequestsPageService',
) -> asyncio.Task:
    task = asyncio.create_task(
        sync_request_statuses_periodically(requests_page_service)
    )
    TaskRegistry.get_instance().register("request-status-sync", task)
    return task


# --- Orphan cover demotion ---

async def demote_orphaned_covers_periodically(
    cover_disk_cache: 'CoverDiskCache',
    library_db: 'LibraryDB',
    interval: int = 86400,
) -> None:
    from repositories.coverart_disk_cache import get_cache_filename

    await asyncio.sleep(300)
    while True:
        try:
            album_mbids = await library_db.get_all_album_mbids()
            artist_mbids = await library_db.get_all_artist_mbids()

            valid_hashes: set[str] = set()
            for mbid in album_mbids:
                for suffix in ("500", "250", "1200", "orig"):
                    valid_hashes.add(get_cache_filename(f"rg_{mbid}", suffix))
            for mbid in artist_mbids:
                for size in ("250", "500"):
                    valid_hashes.add(get_cache_filename(f"artist_{mbid}_{size}", "img"))
                valid_hashes.add(get_cache_filename(f"artist_{mbid}", "img"))

            demoted = await asyncio.to_thread(cover_disk_cache.demote_orphaned, valid_hashes)
            if demoted:
                logger.info("Orphan cover demotion: %d covers demoted to expiring", demoted)
        except asyncio.CancelledError:
            logger.info("Orphan cover demotion task cancelled")
            break
        except Exception as e:
            logger.error("Orphan cover demotion failed: %s", e, exc_info=True)

        await asyncio.sleep(interval)


def start_orphan_cover_demotion_task(
    cover_disk_cache: 'CoverDiskCache',
    library_db: 'LibraryDB',
    interval: int = 86400,
) -> asyncio.Task:
    task = asyncio.create_task(
        demote_orphaned_covers_periodically(cover_disk_cache, library_db, interval=interval)
    )
    TaskRegistry.get_instance().register("orphan-cover-demotion", task)
    return task


# --- Store pruning (request history + ignored releases + youtube orphans) ---

async def prune_stores_periodically(
    request_history: 'RequestHistoryStore',
    mbid_store: 'MBIDStore',
    youtube_store: 'YouTubeStore',
    request_retention_days: int = 180,
    ignored_retention_days: int = 365,
    interval: int = 21600,
) -> None:
    await asyncio.sleep(600)
    while True:
        try:
            pruned_requests = await request_history.prune_old_terminal_requests(request_retention_days)
            pruned_ignored = await mbid_store.prune_old_ignored_releases(ignored_retention_days)
            orphaned_yt = await youtube_store.delete_orphaned_track_links()
            if pruned_requests or pruned_ignored or orphaned_yt:
                logger.info(
                    "Store prune: requests=%d ignored_releases=%d youtube_orphans=%d",
                    pruned_requests, pruned_ignored, orphaned_yt,
                )
        except asyncio.CancelledError:
            logger.info("Store prune task cancelled")
            break
        except Exception as e:
            logger.error("Store prune task failed: %s", e, exc_info=True)

        await asyncio.sleep(interval)


def start_store_prune_task(
    request_history: 'RequestHistoryStore',
    mbid_store: 'MBIDStore',
    youtube_store: 'YouTubeStore',
    request_retention_days: int = 180,
    ignored_retention_days: int = 365,
    interval: int = 21600,
) -> asyncio.Task:
    task = asyncio.create_task(
        prune_stores_periodically(
            request_history, mbid_store, youtube_store,
            request_retention_days=request_retention_days,
            ignored_retention_days=ignored_retention_days,
            interval=interval,
        )
    )
    TaskRegistry.get_instance().register("store-prune", task)
    return task

import logging
import asyncio
import time
from typing import Any, TYPE_CHECKING
from repositories.protocols import LidarrRepositoryProtocol, CoverArtRepositoryProtocol
from api.v1.schemas.library import (
    LibraryAlbum,
    LibraryArtist,
    LibraryGroupedArtist,
    LibraryStatsResponse,
    SyncLibraryResponse,
    AlbumRemovePreviewResponse,
    AlbumRemoveResponse,
    ResolvedTrack,
    TrackResolveResponse,
    TrackResolveRequest,
)
from infrastructure.persistence import LibraryDB, SyncStateStore, GenreIndex
from infrastructure.cache.cache_keys import (
    lidarr_requested_mbids_key,
    SOURCE_RESOLUTION_PREFIX,
    ALBUM_INFO_PREFIX, ARTIST_INFO_PREFIX, LIDARR_PREFIX,
    LIDARR_ALBUM_DETAILS_PREFIX, LIDARR_ALBUM_TRACKS_PREFIX,
    LIDARR_ALBUM_TRACKFILES_PREFIX, LIDARR_ARTIST_ALBUMS_PREFIX,
    LIDARR_ARTIST_DETAILS_PREFIX, LIDARR_ARTIST_IMAGE_PREFIX,
    LIDARR_ALBUM_IMAGE_PREFIX, LIDARR_REQUESTED_PREFIX,
)
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.cover_urls import prefer_release_group_cover_url
from infrastructure.serialization import clone_with_updates
from core.exceptions import ExternalServiceError
from infrastructure.resilience.retry import CircuitOpenError
from services.cache_status_service import CacheStatusService
from services.library_precache_service import LibraryPrecacheService

if TYPE_CHECKING:
    from services.preferences_service import PreferencesService
    from services.local_files_service import LocalFilesService
    from services.jellyfin_library_service import JellyfinLibraryService
    from services.navidrome_library_service import NavidromeLibraryService

logger = logging.getLogger(__name__)

MAX_RESOLVE_ITEMS = 50


class LibraryService:
    def __init__(
        self,
        lidarr_repo: LidarrRepositoryProtocol,
        library_db: LibraryDB,
        cover_repo: CoverArtRepositoryProtocol,
        preferences_service: 'PreferencesService',
        memory_cache: CacheInterface | None = None,
        disk_cache: DiskMetadataCache | None = None,
        artist_discovery_service: Any = None,
        audiodb_image_service: Any = None,
        local_files_service: 'LocalFilesService | None' = None,
        jellyfin_library_service: 'JellyfinLibraryService | None' = None,
        navidrome_library_service: 'NavidromeLibraryService | None' = None,
        sync_state_store: SyncStateStore | None = None,
        genre_index: GenreIndex | None = None,
    ):
        self._lidarr_repo = lidarr_repo
        self._library_db = library_db
        self._cover_repo = cover_repo
        self._preferences_service = preferences_service
        self._memory_cache = memory_cache
        self._disk_cache = disk_cache
        self._local_files_service = local_files_service
        self._jellyfin_library_service = jellyfin_library_service
        self._navidrome_library_service = navidrome_library_service
        self._sync_state_store = sync_state_store
        self._can_precache = sync_state_store is not None and genre_index is not None
        self._precache_service: LibraryPrecacheService | None = None
        if self._can_precache:
            self._precache_service = LibraryPrecacheService(
                lidarr_repo, cover_repo, preferences_service,
                sync_state_store, genre_index, library_db,
                artist_discovery_service=artist_discovery_service,
                audiodb_image_service=audiodb_image_service,
            )
        self._last_sync_time: float = 0.0
        self._last_manual_sync: float = 0.0
        self._manual_sync_cooldown: float = 60.0
        self._global_sync_cooldown: float = 30.0
        self._sync_lock = asyncio.Lock()
        self._sync_future: asyncio.Future | None = None

    def _update_last_sync_timestamp(self) -> None:
        try:
            lidarr_settings = self._preferences_service.get_lidarr_settings()
            updated_settings = clone_with_updates(lidarr_settings, {'last_sync': int(time.time())})
            self._preferences_service.save_lidarr_settings(updated_settings)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to update last_sync timestamp: {e}")

    @staticmethod
    def _normalized_album_cover_url(album_mbid: str | None, cover_url: str | None) -> str | None:
        return prefer_release_group_cover_url(album_mbid, cover_url, size=500)

    async def get_library(self) -> list[LibraryAlbum]:
        try:
            albums_data = await self._library_db.get_albums()
            
            if not albums_data:
                logger.info("Library cache is empty, syncing from Lidarr")
                await self.sync_library()
                albums_data = await self._library_db.get_albums()
            
            albums = [
                LibraryAlbum(
                    artist=album['artist_name'],
                    album=album['title'],
                    year=album.get('year'),
                    monitored=bool(album.get('monitored', 1)),
                    quality=None,
                    cover_url=self._normalized_album_cover_url(
                        album.get('mbid'),
                        album.get('cover_url'),
                    ),
                    musicbrainz_id=album.get('mbid'),
                    artist_mbid=album.get('artist_mbid'),
                    date_added=album.get('date_added')
                )
                for album in albums_data
            ]
            
            return albums
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch library: {e}")
            raise ExternalServiceError(f"Failed to fetch library: {e}")
    
    async def get_library_mbids(self) -> list[str]:
        if not self._lidarr_repo.is_configured():
            return []
        try:
            lidarr_mbids_coro = self._lidarr_repo.get_library_mbids(include_release_ids=False)
            local_mbids_coro = self._library_db.get_all_album_mbids()
            results = await asyncio.gather(
                lidarr_mbids_coro, local_mbids_coro, return_exceptions=True,
            )
            lidarr_mbids = results[0] if not isinstance(results[0], BaseException) else set()
            local_mbids = results[1] if not isinstance(results[1], BaseException) else []
            if isinstance(results[0], BaseException):
                logger.warning("Lidarr library mbids fetch failed, degrading: %s", results[0])
            if isinstance(results[1], BaseException):
                logger.warning("Local library_db mbids fetch failed, degrading: %s", results[1])
            if isinstance(lidarr_mbids, BaseException) and isinstance(local_mbids, BaseException):
                raise ExternalServiceError("Both library mbid sources failed")
            # Union: Lidarr API + local library_db (catches recently-imported
            # albums that Lidarr's cached response may not yet reflect).
            merged = (lidarr_mbids if isinstance(lidarr_mbids, set) else set()) | {m.lower() for m in local_mbids}
            return list(merged)
        except ExternalServiceError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch library mbids: {e}")
            raise ExternalServiceError(f"Failed to fetch library mbids: {e}")

    async def get_requested_mbids(self) -> list[str]:
        if not self._lidarr_repo.is_configured():
            return []
        try:
            requested_set = await self._lidarr_repo.get_requested_mbids()
            return list(requested_set)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch requested mbids: {e}")
            raise ExternalServiceError(f"Failed to fetch requested mbids: {e}")
    
    async def get_artists(self, limit: int | None = None) -> list[LibraryArtist]:
        try:
            artists_data = await self._library_db.get_artists(limit=limit)
            
            if not artists_data:
                logger.info("Artists cache is empty, syncing from Lidarr")
                await self.sync_library()
                artists_data = await self._library_db.get_artists(limit=limit)
            
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
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch artists: {e}")
            raise ExternalServiceError(f"Failed to fetch artists: {e}")

    async def get_albums_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "date_added",
        sort_order: str = "desc",
        search: str | None = None,
    ) -> tuple[list[LibraryAlbum], int]:
        try:
            albums_data, total = await self._library_db.get_albums_paginated(
                limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=search,
            )

            if not albums_data and offset == 0 and not search:
                logger.info("Library cache is empty, syncing from Lidarr")
                await self.sync_library()
                albums_data, total = await self._library_db.get_albums_paginated(
                    limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=search,
                )

            albums = [
                LibraryAlbum(
                    artist=album['artist_name'],
                    album=album['title'],
                    year=album.get('year'),
                    monitored=bool(album.get('monitored', 1)),
                    quality=None,
                    cover_url=self._normalized_album_cover_url(album.get('mbid'), album.get('cover_url')),
                    musicbrainz_id=album.get('mbid'),
                    artist_mbid=album.get('artist_mbid'),
                    date_added=album.get('date_added'),
                )
                for album in albums_data
            ]
            return albums, total
        except (ExternalServiceError, CircuitOpenError):
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch paginated albums: {e}")
            raise ExternalServiceError(f"Failed to fetch paginated albums: {e}")

    async def get_artists_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "name",
        sort_order: str = "asc",
        search: str | None = None,
    ) -> tuple[list[LibraryArtist], int]:
        try:
            artists_data, total = await self._library_db.get_artists_paginated(
                limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=search,
            )

            if not artists_data and offset == 0 and not search:
                logger.info("Artists cache is empty, syncing from Lidarr")
                await self.sync_library()
                artists_data, total = await self._library_db.get_artists_paginated(
                    limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=search,
                )

            artists = [
                LibraryArtist(
                    mbid=artist['mbid'],
                    name=artist['name'],
                    album_count=artist.get('album_count', 0),
                    date_added=artist.get('date_added'),
                )
                for artist in artists_data
            ]
            return artists, total
        except (ExternalServiceError, CircuitOpenError):
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch paginated artists: {e}")
            raise ExternalServiceError(f"Failed to fetch paginated artists: {e}")
    
    async def get_recently_added(self, limit: int = 20) -> list[LibraryAlbum]:

        try:
            if self._lidarr_repo.is_configured():
                albums = await self._lidarr_repo.get_recently_imported(limit=limit)
            else:
                albums = []
            
            if not albums:
                logger.info("No recent imports from history, falling back to cache")
                albums_data = await self._library_db.get_recently_added(limit=limit)
                
                albums = [
                    LibraryAlbum(
                        artist=album['artist_name'],
                        album=album['title'],
                        year=album.get('year'),
                        monitored=bool(album.get('monitored', 1)),
                        quality=None,
                        cover_url=self._normalized_album_cover_url(
                            album.get('mbid'),
                            album.get('cover_url'),
                        ),
                        musicbrainz_id=album.get('mbid'),
                        artist_mbid=album.get('artist_mbid'),
                        date_added=album.get('date_added')
                    )
                    for album in albums_data
                ]
            
            return albums
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch recently added: {e}")
            raise ExternalServiceError(f"Failed to fetch recently added: {e}")
    
    async def sync_library(self, is_manual: bool = False, force_full: bool = False) -> SyncLibraryResponse:
        from services.cache_status_service import CacheStatusService

        if not self._lidarr_repo.is_configured():
            raise ExternalServiceError("Lidarr is not configured. Set a Lidarr API key in Settings to sync your library.")

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
                    if is_manual:
                        logger.warning("Library sync already in progress - cancelling previous sync to start fresh")
                        await status_service.cancel_current_sync()
                        await status_service.wait_for_completion()
                    else:
                        logger.info("Library sync already in progress - skipping auto-sync")
                        return SyncLibraryResponse(status="skipped", artists=0, albums=0)

                if self._sync_future is not None and not self._sync_future.done():
                    existing_future = self._sync_future
                else:
                    existing_future = None
                    loop = asyncio.get_running_loop()
                    self._sync_future = loop.create_future()

            # Shield so waiter cancellation doesn't poison the shared future
            if existing_future is not None:
                return await asyncio.shield(existing_future)
            
            sync_succeeded = False
            try:
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
                        'cover_url': self._normalized_album_cover_url(
                            album.musicbrainz_id,
                            album.cover_url,
                        ),
                        'monitored': album.monitored,
                        'date_added': album.date_added
                    }
                    for album in albums
                ]
                
                await self._library_db.save_library(artists, albums_data)
                logger.info("Library cache updated - unmonitored items removed")

                now = time.time()
                self._last_sync_time = now
                if is_manual:
                    self._last_manual_sync = now

                if self._precache_service is None:
                    logger.warning("Precache skipped: sync_state_store/genre_index not provided")
                    self._update_last_sync_timestamp()
                    result = SyncLibraryResponse(status='success', artists=len(artists), albums=len(albums))
                    self._sync_future.set_result(result)
                    return result

                resume = False
                if not force_full and self._sync_state_store:
                    try:
                        last_state = await self._sync_state_store.get_sync_state()
                        if last_state and last_state.get('status') == 'failed':
                            resume = True
                            logger.info("Previous sync failed, resuming from checkpoint")
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Failed to check sync state for resume: %s", e)

                if force_full and self._sync_state_store:
                    try:
                        await self._sync_state_store.clear_processed_items()
                        await self._sync_state_store.clear_sync_state()
                        logger.info("Force full sync: cleared previous progress")
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Failed to clear sync state for force_full: %s", e)

                task = asyncio.create_task(self._precache_service.precache_library_resources(artists, albums, resume=resume))

                def on_task_done(t: asyncio.Task):
                    try:
                        exc = t.exception()
                        if exc:
                            logger.error(f"Precache task failed: {exc}")
                            task_success = False
                        else:
                            task_success = not t.cancelled()
                    except asyncio.CancelledError:
                        logger.info("Precache task was cancelled")
                        task_success = False
                    finally:
                        status_service.set_current_task(None)
                        try:
                            lidarr_settings = self._preferences_service.get_lidarr_settings()
                            if sync_started_at >= (lidarr_settings.last_sync or 0):
                                updated = clone_with_updates(lidarr_settings, {
                                    'last_sync_success': task_success,
                                })
                                self._preferences_service.save_lidarr_settings(updated)
                        except Exception as e:  # noqa: BLE001
                            logger.warning(f"Failed to update last_sync_success: {e}")

                task.add_done_callback(on_task_done)
                status_service.set_current_task(task)

                logger.info(f"Library sync complete: {len(artists)} artists, {len(albums)} albums")

                self._update_last_sync_timestamp()
                sync_started_at = self._preferences_service.get_lidarr_settings().last_sync or 0

                result = SyncLibraryResponse(
                    status='success',
                    artists=len(artists),
                    albums=len(albums),
                )
                sync_succeeded = True
                self._sync_future.set_result(result)
                return result
            except BaseException as exc:
                if self._sync_future is not None and not self._sync_future.done():
                    self._sync_future.set_exception(exc)
                raise
            finally:
                if not sync_succeeded:
                    future = self._sync_future
                    self._sync_future = None
                    # Suppress "Future exception was never retrieved" if no waiter
                    if future is not None and future.done() and not future.cancelled():
                        try:
                            future.exception()
                        except BaseException:
                            pass
        except (ExternalServiceError, CircuitOpenError):
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Couldn't sync the library: {e}")
            raise ExternalServiceError(f"Couldn't sync the library: {e}")

    async def get_stats(self) -> LibraryStatsResponse:
        try:
            stats = await self._library_db.get_stats()
            
            return LibraryStatsResponse(
                artist_count=stats['artist_count'],
                album_count=stats['album_count'],
                last_sync=stats['last_sync'],
                db_size_bytes=stats['db_size_bytes'],
                db_size_mb=round(stats['db_size_bytes'] / (1024 * 1024), 2)
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch library stats: {e}")
            raise ExternalServiceError(f"Failed to fetch library stats: {e}")
    
    async def clear_cache(self) -> None:
        try:
            await self._library_db.clear()
            logger.info("Library cache cleared")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to clear library cache: {e}")
            raise ExternalServiceError(f"Failed to clear library cache: {e}")
    
    async def get_library_grouped(self) -> list[LibraryGroupedArtist]:
        if not self._lidarr_repo.is_configured():
            return []
        try:
            return await self._lidarr_repo.get_library_grouped()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch grouped library: {e}")
            raise ExternalServiceError(f"Failed to fetch grouped library: {e}")

    async def get_album_removal_preview(self, album_mbid: str) -> AlbumRemovePreviewResponse:
        try:
            album_data = await self._lidarr_repo.get_album_details(album_mbid)
            if not album_data or not album_data.get("id"):
                raise ExternalServiceError(f"Album not found in Lidarr: {album_mbid}")

            artist_mbid = album_data.get("artist_mbid")
            artist_name = album_data.get("artist_name", "Unknown")

            artist_will_be_removed = False
            if artist_mbid:
                artist_albums = await self._lidarr_repo.get_artist_albums(artist_mbid)
                monitored_count = sum(1 for album in artist_albums if album.get("monitored"))
                artist_will_be_removed = monitored_count <= 1

            return AlbumRemovePreviewResponse(
                success=True,
                artist_will_be_removed=artist_will_be_removed,
                artist_name=artist_name if artist_will_be_removed else None,
            )
        except ExternalServiceError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to build removal preview for album {album_mbid}: {e}")
            raise ExternalServiceError(f"Failed to load removal preview: {e}")

    async def remove_album(self, album_mbid: str, delete_files: bool = False) -> AlbumRemoveResponse:
        try:
            album_data = await self._lidarr_repo.get_album_details(album_mbid)
            if not album_data or not album_data.get("id"):
                raise ExternalServiceError(f"Album not found in Lidarr: {album_mbid}")

            album_id = album_data["id"]
            artist_mbid = album_data.get("artist_mbid")
            artist_name = album_data.get("artist_name", "Unknown")

            await self._lidarr_repo.delete_album(album_id, delete_files=delete_files)

            artist_removed = False
            if artist_mbid:
                try:
                    if self._memory_cache:
                        await asyncio.gather(
                            self._memory_cache.delete(f"lidarr_artist_albums:{artist_mbid}"),
                            self._memory_cache.delete(f"lidarr_artist_details:{artist_mbid}"),
                        )
                    artist_albums = await self._lidarr_repo.get_artist_albums(artist_mbid)
                    if not any(a.get("monitored") for a in artist_albums):
                        artist_details = await self._lidarr_repo.get_artist_details(artist_mbid)
                        if artist_details and artist_details.get("id"):
                            await self._lidarr_repo.delete_artist(
                                artist_details["id"], delete_files=delete_files
                            )
                            artist_removed = True
                            logger.info(f"Auto-removed artist '{artist_name}' (no remaining albums)")
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"Album '{album_mbid}' removed but artist cleanup failed for '{artist_mbid}': {e}"
                    )

            try:
                await self._invalidate_caches_after_removal(album_mbid, artist_mbid, artist_removed=artist_removed)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Album '{album_mbid}' removed but cache invalidation failed: {e}")

            return AlbumRemoveResponse(
                success=True,
                artist_removed=artist_removed,
                artist_name=artist_name if artist_removed else None,
            )
        except ExternalServiceError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Couldn't remove album {album_mbid}: {e}")
            raise ExternalServiceError(f"Couldn't remove this album: {e}")

    async def _invalidate_caches_after_removal(self, album_mbid: str, artist_mbid: str | None, *, artist_removed: bool = False) -> None:
        await self._library_db.clear()

        if self._memory_cache:
            keys_to_delete = [
                f"{ALBUM_INFO_PREFIX}{album_mbid}",
                f"{LIDARR_ALBUM_DETAILS_PREFIX}{album_mbid}",
                lidarr_requested_mbids_key(),
            ]
            if artist_mbid:
                keys_to_delete.extend([
                    f"{LIDARR_ARTIST_ALBUMS_PREFIX}{artist_mbid}",
                    f"{LIDARR_ARTIST_DETAILS_PREFIX}{artist_mbid}",
                    f"{ARTIST_INFO_PREFIX}{artist_mbid}",
                ])
            await asyncio.gather(
                *[self._memory_cache.delete(k) for k in keys_to_delete],
                self._memory_cache.clear_prefix(f"{LIDARR_PREFIX}library:"),
                self._memory_cache.clear_prefix(f"{LIDARR_PREFIX}artists:"),
                self._memory_cache.clear_prefix(LIDARR_ALBUM_IMAGE_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_ALBUM_DETAILS_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_ALBUM_TRACKS_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_ALBUM_TRACKFILES_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_REQUESTED_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_ARTIST_IMAGE_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_ARTIST_DETAILS_PREFIX),
                self._memory_cache.clear_prefix(LIDARR_ARTIST_ALBUMS_PREFIX),
            )

        if self._disk_cache:
            coros = [self._disk_cache.delete_album(album_mbid)]
            if artist_mbid:
                coros.append(self._disk_cache.delete_artist(artist_mbid))
            await asyncio.gather(*coros)

        if self._cover_repo:
            try:
                await self._cover_repo.delete_covers_for_album(album_mbid)
                if artist_mbid and artist_removed:
                    await self._cover_repo.delete_covers_for_artist(artist_mbid)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to clean up cover images after removal", exc_info=True)

    async def _resolve_album_tracks(
        self,
        album_mbid: str,
    ) -> dict[str, tuple[str, str, str | None, float | None]]:
        """Resolve album MBID to {disc:track: (source, source_id, format, duration)}.

        Priority: local → navidrome → jellyfin.
        Uses source_resolution cache (1h TTL).
        """
        if self._memory_cache is None:
            raise ExternalServiceError("Memory cache not available for track resolution")

        cache_key = f"{SOURCE_RESOLUTION_PREFIX}_tracks:{album_mbid}"
        cached = await self._memory_cache.get(cache_key)
        if cached is not None:
            return cached

        result: dict[str, tuple[str, str, str | None, float | None]] = {}

        def _track_key(disc: int, track: int) -> str:
            return f"{disc}:{track}"

        if self._local_files_service:
            try:
                match = await self._local_files_service.match_album_by_mbid(album_mbid)
                if match.found:
                    for t in match.tracks:
                        key = _track_key(getattr(t, "disc_number", 1) or 1, t.track_number)
                        if key not in result:
                            result[key] = (
                                "local",
                                str(t.track_file_id),
                                t.format or None,
                                t.duration_seconds,
                            )
            except Exception:  # noqa: BLE001
                logger.debug("Local track resolution failed for %s", album_mbid, exc_info=True)

        nd_enabled = False
        try:
            nd_settings = self._preferences_service.get_navidrome_connection_raw()
            nd_enabled = nd_settings.enabled
        except AttributeError:
            logger.debug("Navidrome settings unavailable during track resolution", exc_info=True)

        if nd_enabled and self._navidrome_library_service:
            try:
                nav_id = self._navidrome_library_service.lookup_navidrome_id(album_mbid)
                if nav_id:
                    detail = await self._navidrome_library_service.get_album_detail(nav_id)
                    if detail:
                        for t in detail.tracks:
                            key = _track_key(getattr(t, "disc_number", 1) or 1, t.track_number)
                            if key not in result:
                                result[key] = (
                                    "navidrome",
                                    t.navidrome_id,
                                    t.codec,
                                    t.duration_seconds,
                                )
            except Exception:  # noqa: BLE001
                logger.debug("Navidrome track resolution failed for %s", album_mbid, exc_info=True)

        jf_enabled = False
        try:
            jf_settings = self._preferences_service.get_jellyfin_connection()
            jf_enabled = jf_settings.enabled
        except AttributeError:
            logger.debug("Jellyfin settings unavailable during track resolution", exc_info=True)

        if jf_enabled and self._jellyfin_library_service:
            try:
                match = await self._jellyfin_library_service.match_album_by_mbid(album_mbid)
                if match.found:
                    all_same = len(match.tracks) > 1 and len({t.track_number for t in match.tracks}) == 1
                    if not all_same:
                        for t in match.tracks:
                            key = _track_key(getattr(t, "disc_number", 1) or 1, t.track_number)
                            if key not in result:
                                result[key] = (
                                    "jellyfin",
                                    t.jellyfin_id,
                                    t.codec,
                                    t.duration_seconds,
                                )
            except Exception:  # noqa: BLE001
                logger.debug("Jellyfin track resolution failed for %s", album_mbid, exc_info=True)

        await self._memory_cache.set(cache_key, result, ttl_seconds=3600)
        return result

    async def resolve_tracks_batch(
        self,
        items: list,
    ) -> TrackResolveResponse:
        """Resolve a batch of track items to stream URLs."""
        items = items[:MAX_RESOLVE_ITEMS]
        if not items:
            return TrackResolveResponse(items=[])

        album_mbids = {it.release_group_mbid for it in items if it.release_group_mbid}

        sem = asyncio.Semaphore(5)

        async def _resolve_one(mbid: str) -> tuple[str, dict]:
            async with sem:
                return mbid, await self._resolve_album_tracks(mbid)

        tasks = [_resolve_one(mbid) for mbid in album_mbids]
        album_maps: dict[str, dict] = {}
        for r in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(r, Exception):
                logger.warning("Album resolution failed: %s", r)
                continue
            mbid, track_map = r
            album_maps[mbid] = track_map

        resolved: list[ResolvedTrack] = []
        for item in items:
            base = ResolvedTrack(
                release_group_mbid=item.release_group_mbid,
                disc_number=item.disc_number,
                track_number=item.track_number,
            )

            if not item.release_group_mbid or item.track_number is None:
                resolved.append(base)
                continue

            track_map = album_maps.get(item.release_group_mbid, {})
            lookup_key = f"{item.disc_number or 1}:{item.track_number}"
            match = track_map.get(lookup_key)
            if not match:
                resolved.append(base)
                continue

            source, source_id, fmt, duration = match
            stream_url = None
            if source == "local":
                stream_url = f"/api/v1/stream/local/{source_id}"
            elif source == "navidrome":
                stream_url = f"/api/v1/stream/navidrome/{source_id}"
            elif source == "jellyfin":
                stream_url = f"/api/v1/stream/jellyfin/{source_id}"

            resolved.append(ResolvedTrack(
                release_group_mbid=item.release_group_mbid,
                disc_number=item.disc_number,
                track_number=item.track_number,
                source=source,
                track_source_id=source_id,
                stream_url=stream_url,
                format=fmt,
                duration=duration,
            ))

        return TrackResolveResponse(items=resolved)

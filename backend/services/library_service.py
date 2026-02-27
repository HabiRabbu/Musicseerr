import logging
import asyncio
import time
from typing import Any, TYPE_CHECKING
from repositories.protocols import LidarrRepositoryProtocol, CoverArtRepositoryProtocol
from api.v1.schemas.library import LibraryAlbum, LibraryArtist, LibraryStatsResponse
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.cover_urls import prefer_release_group_cover_url
from core.exceptions import ExternalServiceError
from services.cache_status_service import CacheStatusService
from services.library_precache_service import LibraryPrecacheService

if TYPE_CHECKING:
    from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(
        self,
        lidarr_repo: LidarrRepositoryProtocol,
        library_cache: LibraryCache,
        cover_repo: CoverArtRepositoryProtocol,
        preferences_service: 'PreferencesService',
        memory_cache: CacheInterface | None = None,
        disk_cache: DiskMetadataCache | None = None,
        artist_discovery_service: Any = None,
    ):
        self._lidarr_repo = lidarr_repo
        self._library_cache = library_cache
        self._cover_repo = cover_repo
        self._preferences_service = preferences_service
        self._memory_cache = memory_cache
        self._disk_cache = disk_cache
        self._precache_service = LibraryPrecacheService(
            lidarr_repo, cover_repo, preferences_service, library_cache,
            artist_discovery_service=artist_discovery_service,
        )
        self._last_sync_time: float = 0.0
        self._last_manual_sync: float = 0.0
        self._manual_sync_cooldown: float = 60.0
        self._global_sync_cooldown: float = 30.0
        self._sync_lock = asyncio.Lock()

    def _update_last_sync_timestamp(self) -> None:
        try:
            lidarr_settings = self._preferences_service.get_lidarr_settings()
            updated_settings = lidarr_settings.model_copy(update={'last_sync': int(time.time())})
            self._preferences_service.save_lidarr_settings(updated_settings)
        except Exception as e:
            logger.warning(f"Failed to update last_sync timestamp: {e}")

    @staticmethod
    def _normalized_album_cover_url(album_mbid: str | None, cover_url: str | None) -> str | None:
        return prefer_release_group_cover_url(album_mbid, cover_url, size=500)

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

    async def get_requested_mbids(self) -> list[str]:
        try:
            requested_set = await self._lidarr_repo.get_requested_mbids()
            return list(requested_set)
        except Exception as e:
            logger.error(f"Failed to fetch requested mbids: {e}")
            raise ExternalServiceError(f"Failed to fetch requested mbids: {e}")
    
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
        except Exception as e:
            logger.error(f"Failed to fetch recently added: {e}")
            raise ExternalServiceError(f"Failed to fetch recently added: {e}")
    
    async def sync_library(self, is_manual: bool = False) -> dict:
        from services.cache_status_service import CacheStatusService

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
                    'cover_url': self._normalized_album_cover_url(
                        album.musicbrainz_id,
                        album.cover_url,
                    ),
                    'monitored': album.monitored,
                    'date_added': album.date_added
                }
                for album in albums
            ]
            
            await self._library_cache.save_library(artists, albums_data)
            logger.info("Library cache updated - unmonitored items removed")

            task = asyncio.create_task(self._precache_service.precache_library_resources(artists, albums))

            def on_task_done(t: asyncio.Task):
                try:
                    exc = t.exception()
                    if exc:
                        logger.error(f"Precache task failed: {exc}")
                except asyncio.CancelledError:
                    logger.info("Precache task was cancelled")
                finally:
                    status_service.set_current_task(None)

            task.add_done_callback(on_task_done)
            status_service.set_current_task(task)

            logger.info(f"Library sync complete: {len(artists)} artists, {len(albums)} albums")

            self._update_last_sync_timestamp()

            return {
                'status': 'success',
                'artists': len(artists),
                'albums': len(albums)
            }
        except Exception as e:
            logger.error(f"Failed to sync library: {e}")
            raise ExternalServiceError(f"Failed to sync library: {e}")

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

    async def get_album_removal_preview(self, album_mbid: str) -> dict:
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

            return {
                "success": True,
                "artist_will_be_removed": artist_will_be_removed,
                "artist_name": artist_name if artist_will_be_removed else None,
            }
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to build removal preview for album {album_mbid}: {e}")
            raise ExternalServiceError(f"Failed to load removal preview: {e}")

    async def remove_album(self, album_mbid: str, delete_files: bool = False) -> dict:
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
                except Exception as e:
                    logger.warning(
                        f"Album '{album_mbid}' removed but artist cleanup failed for '{artist_mbid}': {e}"
                    )

            try:
                await self._invalidate_caches_after_removal(album_mbid, artist_mbid)
            except Exception as e:
                logger.warning(f"Album '{album_mbid}' removed but cache invalidation failed: {e}")

            return {
                "success": True,
                "artist_removed": artist_removed,
                "artist_name": artist_name if artist_removed else None,
            }
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to remove album {album_mbid}: {e}")
            raise ExternalServiceError(f"Failed to remove album: {e}")

    async def _invalidate_caches_after_removal(self, album_mbid: str, artist_mbid: str | None) -> None:
        await self._library_cache.clear()

        if self._memory_cache:
            keys_to_delete = [
                f"album_info:{album_mbid}",
                f"lidarr_album_details:{album_mbid}",
                "lidarr_requested_mbids",
            ]
            if artist_mbid:
                keys_to_delete.extend([
                    f"lidarr_artist_albums:{artist_mbid}",
                    f"lidarr_artist_details:{artist_mbid}",
                    f"artist_info:{artist_mbid}",
                ])
            await asyncio.gather(
                *[self._memory_cache.delete(k) for k in keys_to_delete],
                self._memory_cache.clear_prefix("lidarr:library:mbids:"),
                self._memory_cache.clear_prefix("lidarr:artists:mbids"),
                self._memory_cache.clear_prefix("lidarr_album"),
                self._memory_cache.clear_prefix("lidarr_requested"),
                self._memory_cache.clear_prefix("lidarr_artist"),
            )

        if self._disk_cache:
            coros = [self._disk_cache.delete_album(album_mbid)]
            if artist_mbid:
                coros.append(self._disk_cache.delete_artist(artist_mbid))
            await asyncio.gather(*coros)

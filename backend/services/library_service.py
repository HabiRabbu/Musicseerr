import logging
import asyncio
import time
from typing import Any, TYPE_CHECKING
from repositories.protocols import LidarrRepositoryProtocol, CoverArtRepositoryProtocol
from api.v1.schemas.library import LibraryAlbum, LibraryArtist, LibraryStatsResponse
from infrastructure.cache.persistent_cache import LibraryCache
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
        preferences_service: 'PreferencesService'
    ):
        self._lidarr_repo = lidarr_repo
        self._library_cache = library_cache
        self._cover_repo = cover_repo
        self._preferences_service = preferences_service
        self._precache_service = LibraryPrecacheService(lidarr_repo, cover_repo, preferences_service, library_cache)
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

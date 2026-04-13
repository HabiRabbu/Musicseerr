import logging
import asyncio
import time
from typing import Optional, TYPE_CHECKING
import msgspec
from api.v1.schemas.album import AlbumInfo, AlbumBasicInfo, AlbumTracksInfo, Track
from repositories.protocols import LidarrRepositoryProtocol, MusicBrainzRepositoryProtocol
from services.preferences_service import PreferencesService
from services.album_utils import parse_year, find_primary_release, get_ranked_releases, extract_artist_info, extract_tracks, extract_label, build_album_basic_info, lidarr_to_basic_info, mb_to_basic_info
from infrastructure.persistence import LibraryDB
from infrastructure.cache.cache_keys import ALBUM_INFO_PREFIX, LIDARR_ALBUM_DETAILS_PREFIX
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.cover_urls import prefer_release_group_cover_url
from infrastructure.validators import validate_mbid
from core.exceptions import ResourceNotFoundError
from services.audiodb_image_service import AudioDBImageService
from repositories.audiodb_models import AudioDBAlbumImages

if TYPE_CHECKING:
    from services.audiodb_browse_queue import AudioDBBrowseQueue

logger = logging.getLogger(__name__)


class AlbumService:
    def __init__(
        self, 
        lidarr_repo: LidarrRepositoryProtocol, 
        mb_repo: MusicBrainzRepositoryProtocol,
        library_db: LibraryDB,
        memory_cache: CacheInterface,
        disk_cache: DiskMetadataCache,
        preferences_service: PreferencesService,
        audiodb_image_service: AudioDBImageService | None = None,
        audiodb_browse_queue: 'AudioDBBrowseQueue | None' = None,
    ):
        self._lidarr_repo = lidarr_repo
        self._mb_repo = mb_repo
        self._library_db = library_db
        self._cache = memory_cache
        self._disk_cache = disk_cache
        self._preferences_service = preferences_service
        self._audiodb_image_service = audiodb_image_service
        self._audiodb_browse_queue = audiodb_browse_queue
        self._revalidation_timestamps: dict[str, float] = {}
        self._album_in_flight: dict[str, asyncio.Future[AlbumInfo]] = {}

    async def _get_audiodb_album_thumb(self, release_group_id: str, artist_name: str | None = None, album_name: str | None = None, *, allow_fetch: bool = False) -> str | None:
        if self._audiodb_image_service is None:
            return None
        try:
            if allow_fetch:
                images = await self._audiodb_image_service.fetch_and_cache_album_images(
                    release_group_id, artist_name, album_name, is_monitored=False,
                )
            else:
                images = await self._audiodb_image_service.get_cached_album_images(release_group_id)
            if images and not images.is_negative:
                return images.album_thumb_url
            if not allow_fetch and images is None and self._audiodb_browse_queue:
                settings = self._preferences_service.get_advanced_settings()
                if settings.audiodb_enabled:
                    await self._audiodb_browse_queue.enqueue(
                        "album", release_group_id,
                        name=album_name, artist_name=artist_name,
                    )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to get AudioDB album thumb for %s: %s", release_group_id[:8], e)
        return None

    async def _apply_audiodb_album_images(
        self,
        album_info: AlbumInfo,
        release_group_mbid: str,
        artist_name: str | None,
        album_name: str | None,
        *,
        allow_fetch: bool = False,
        is_monitored: bool = False,
    ) -> AlbumInfo:
        if self._audiodb_image_service is None:
            return album_info
        try:
            images: AudioDBAlbumImages | None
            if allow_fetch:
                images = await self._audiodb_image_service.fetch_and_cache_album_images(
                    release_group_mbid, artist_name, album_name, is_monitored=is_monitored,
                )
            else:
                images = await self._audiodb_image_service.get_cached_album_images(release_group_mbid)
            if images is None or images.is_negative:
                if not allow_fetch and images is None and self._audiodb_browse_queue:
                    settings = self._preferences_service.get_advanced_settings()
                    if settings.audiodb_enabled:
                        await self._audiodb_browse_queue.enqueue(
                            "album", release_group_mbid,
                            name=album_name, artist_name=artist_name,
                        )
                return album_info
            album_info.album_thumb_url = images.album_thumb_url
            album_info.album_back_url = images.album_back_url
            album_info.album_cdart_url = images.album_cdart_url
            album_info.album_spine_url = images.album_spine_url
            album_info.album_3d_case_url = images.album_3d_case_url
            album_info.album_3d_flat_url = images.album_3d_flat_url
            album_info.album_3d_face_url = images.album_3d_face_url
            album_info.album_3d_thumb_url = images.album_3d_thumb_url
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to apply AudioDB images for album %s: %s", release_group_mbid[:8], e)
        return album_info

    async def is_album_cached(self, release_group_id: str) -> bool:
        cache_key = f"{ALBUM_INFO_PREFIX}{release_group_id}"
        return await self._cache.get(cache_key) is not None

    async def _get_queued_mbids(self) -> set[str]:
        try:
            queue_items = await self._lidarr_repo.get_queue()
            return {item.musicbrainz_id.lower() for item in queue_items if item.musicbrainz_id}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to fetch queue: {e}")
            return set()
    
    async def _get_cached_album_info(self, release_group_id: str, cache_key: str) -> Optional[AlbumInfo]:
        cached_info = await self._cache.get(cache_key)
        if cached_info:
            return await self._revalidate_library_status(release_group_id, cached_info)
        
        disk_data = await self._disk_cache.get_album(release_group_id)
        if disk_data:
            album_info = msgspec.convert(disk_data, AlbumInfo, strict=False)
            album_info = await self._revalidate_library_status(release_group_id, album_info)
            advanced_settings = self._preferences_service.get_advanced_settings()
            ttl = advanced_settings.cache_ttl_album_library if album_info.in_library else advanced_settings.cache_ttl_album_non_library
            await self._cache.set(cache_key, album_info, ttl_seconds=ttl)
            return album_info
        
        return None

    async def _revalidate_library_status(self, release_group_id: str, album_info: AlbumInfo) -> AlbumInfo:
        _REVALIDATION_COOLDOWN = 60
        if not self._lidarr_repo.is_configured():
            return album_info
        now = time.monotonic()
        last = self._revalidation_timestamps.get(release_group_id, 0.0)
        if now - last < _REVALIDATION_COOLDOWN:
            return album_info

        lidarr_album = await self._lidarr_repo.get_album_details(release_group_id)
        if lidarr_album is None:
            return album_info

        self._revalidation_timestamps[release_group_id] = time.monotonic()
        current_in_library = self._check_lidarr_in_library(lidarr_album)
        if current_in_library != album_info.in_library:
            album_info.in_library = current_in_library
            await self._save_album_to_cache(release_group_id, album_info)
        return album_info

    async def _save_album_to_cache(self, release_group_id: str, album_info: AlbumInfo) -> None:
        cache_key = f"{ALBUM_INFO_PREFIX}{release_group_id}"
        advanced_settings = self._preferences_service.get_advanced_settings()
        ttl = advanced_settings.cache_ttl_album_library if album_info.in_library else advanced_settings.cache_ttl_album_non_library
        await self._cache.set(cache_key, album_info, ttl_seconds=ttl)
        await self._disk_cache.set_album(release_group_id, album_info, is_monitored=album_info.in_library, ttl_seconds=ttl if not album_info.in_library else None)

    def _check_lidarr_in_library(self, lidarr_album: dict | None) -> bool:
        if lidarr_album and lidarr_album.get("monitored", False):
            statistics = lidarr_album.get("statistics", {})
            return statistics.get("trackFileCount", 0) > 0
        return False

    async def warm_full_album_cache(self, release_group_id: str) -> None:
        """Fire-and-forget: populate the full album_info cache if missing."""
        try:
            cache_key = f"{ALBUM_INFO_PREFIX}{release_group_id}"
            if await self._get_cached_album_info(release_group_id, cache_key):
                return
            await self.get_album_info(release_group_id)
        except Exception:  # noqa: BLE001
            pass

    async def refresh_album(self, release_group_id: str) -> AlbumInfo:
        release_group_id = validate_mbid(release_group_id, "album")

        await self._cache.delete(f"{ALBUM_INFO_PREFIX}{release_group_id}")
        await self._cache.delete(f"{LIDARR_ALBUM_DETAILS_PREFIX}{release_group_id}")
        await self._disk_cache.delete_album(release_group_id)
        self._revalidation_timestamps.pop(release_group_id, None)
        self._album_in_flight.pop(release_group_id, None)

        return await self.get_album_info(release_group_id)

    async def get_album_info(self, release_group_id: str, monitored_mbids: set[str] = None) -> AlbumInfo:
        try:
            release_group_id = validate_mbid(release_group_id, "album")
        except ValueError as e:
            logger.error(f"Invalid album MBID: {e}")
            raise
        try:
            cache_key = f"{ALBUM_INFO_PREFIX}{release_group_id}"
            cached = await self._get_cached_album_info(release_group_id, cache_key)
            if cached:
                cached = await self._apply_audiodb_album_images(
                    cached, release_group_id, cached.artist_name, cached.title,
                    allow_fetch=True, is_monitored=cached.in_library,
                )
                return cached

            if release_group_id in self._album_in_flight:
                return await asyncio.shield(self._album_in_flight[release_group_id])

            loop = asyncio.get_running_loop()
            future: asyncio.Future[AlbumInfo] = loop.create_future()
            self._album_in_flight[release_group_id] = future
            try:
                album_info = await self._do_get_album_info(release_group_id, cache_key, monitored_mbids)
                if not future.done():
                    future.set_result(album_info)
                return album_info
            except BaseException as exc:
                if not future.done():
                    future.set_exception(exc)
                raise
            finally:
                self._album_in_flight.pop(release_group_id, None)
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"API call failed for album {release_group_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get album info: {e}")

    async def _do_get_album_info(
        self, release_group_id: str, cache_key: str, monitored_mbids: set[str] | None
    ) -> AlbumInfo:
        lidarr_album = await self._lidarr_repo.get_album_details(release_group_id) if self._lidarr_repo.is_configured() else None
        in_library = self._check_lidarr_in_library(lidarr_album)
        if in_library and lidarr_album:
            album_info = await self._build_album_from_lidarr(release_group_id, lidarr_album)
        else:
            album_info = await self._build_album_from_musicbrainz(release_group_id, monitored_mbids)
        album_info = await self._apply_audiodb_album_images(
            album_info, release_group_id, album_info.artist_name, album_info.title,
            allow_fetch=True, is_monitored=album_info.in_library,
        )
        await self._save_album_to_cache(release_group_id, album_info)
        return album_info
    
    async def get_album_basic_info(self, release_group_id: str) -> AlbumBasicInfo:
        try:
            release_group_id = validate_mbid(release_group_id, "album")
        except ValueError as e:
            logger.error(f"Invalid album MBID: {e}")
            raise

        try:
            cache_key = f"{ALBUM_INFO_PREFIX}{release_group_id}"

            try:
                if self._lidarr_repo.is_configured():
                    requested_mbids = await self._lidarr_repo.get_requested_mbids()
                else:
                    requested_mbids = set()
            except Exception:  # noqa: BLE001
                logger.warning("Lidarr unavailable, proceeding without requested data")
                requested_mbids = set()
            is_requested = release_group_id.lower() in requested_mbids

            cached_album_info = await self._get_cached_album_info(release_group_id, cache_key)
            if cached_album_info:
                album_thumb = cached_album_info.album_thumb_url
                if not album_thumb:
                    album_thumb = await self._get_audiodb_album_thumb(
                        release_group_id, cached_album_info.artist_name, cached_album_info.title,
                        allow_fetch=False,
                    )
                return AlbumBasicInfo(
                    title=cached_album_info.title,
                    musicbrainz_id=cached_album_info.musicbrainz_id,
                    artist_name=cached_album_info.artist_name,
                    artist_id=cached_album_info.artist_id,
                    release_date=cached_album_info.release_date,
                    year=cached_album_info.year,
                    type=cached_album_info.type,
                    disambiguation=cached_album_info.disambiguation,
                    in_library=cached_album_info.in_library,
                    requested=is_requested and not cached_album_info.in_library,
                    cover_url=cached_album_info.cover_url,
                    album_thumb_url=album_thumb,
                )

            lidarr_album = await self._lidarr_repo.get_album_details(release_group_id) if self._lidarr_repo.is_configured() else None
            in_library = self._check_lidarr_in_library(lidarr_album)
            if lidarr_album and lidarr_album.get("monitored", False):
                basic = AlbumBasicInfo(**lidarr_to_basic_info(lidarr_album, release_group_id, in_library, is_requested=is_requested))
                if not basic.album_thumb_url:
                    basic.album_thumb_url = await self._get_audiodb_album_thumb(
                        release_group_id, basic.artist_name, basic.title,
                        allow_fetch=False,
                    )
                return basic
            release_group = await self._fetch_release_group(release_group_id)
            if lidarr_album is None:
                cached_album = await self._library_db.get_album_by_mbid(release_group_id)
                in_library = cached_album is not None
            basic = AlbumBasicInfo(**mb_to_basic_info(release_group, release_group_id, in_library, is_requested))
            basic.album_thumb_url = await self._get_audiodb_album_thumb(
                release_group_id, basic.artist_name, basic.title,
                allow_fetch=False,
            )
            return basic
        
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to get basic album info for {release_group_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get album info: {e}")
    
    async def get_album_tracks_info(self, release_group_id: str) -> AlbumTracksInfo:
        try:
            release_group_id = validate_mbid(release_group_id, "album")
        except ValueError as e:
            logger.error(f"Invalid album MBID: {e}")
            raise
        
        try:
            cache_key = f"{ALBUM_INFO_PREFIX}{release_group_id}"
            cached_album_info = await self._get_cached_album_info(release_group_id, cache_key)
            if cached_album_info:
                return AlbumTracksInfo(
                    tracks=cached_album_info.tracks,
                    total_tracks=cached_album_info.total_tracks,
                    total_length=cached_album_info.total_length,
                    label=cached_album_info.label,
                    barcode=cached_album_info.barcode,
                    country=cached_album_info.country,
                )
            
            lidarr_album = await self._lidarr_repo.get_album_details(release_group_id) if self._lidarr_repo.is_configured() else None
            in_library = lidarr_album is not None and lidarr_album.get("monitored", False)
            
            if in_library and lidarr_album:
                album_id = lidarr_album.get("id")
                tracks = []
                total_length = 0
                
                if album_id:
                    lidarr_tracks = await self._lidarr_repo.get_album_tracks(album_id)
                    for t in lidarr_tracks:
                        duration_ms = t.get("duration_ms", 0)
                        if duration_ms:
                            total_length += duration_ms
                        tracks.append(Track(
                            position=int(t.get("track_number") or t.get("position", 0)),
                            disc_number=int(t.get("disc_number", 1) or 1),
                            title=t.get("title", "Unknown"),
                            length=duration_ms if duration_ms else None,
                            recording_id=None,
                        ))
                
                return AlbumTracksInfo(
                    tracks=tracks,
                    total_tracks=len(tracks),
                    total_length=total_length if total_length > 0 else None,
                    label=None,
                    barcode=None,
                    country=None,
                )
            
            release_group = await self._fetch_release_group(release_group_id)
            ranked_releases = get_ranked_releases(release_group)
            
            if not ranked_releases:
                return AlbumTracksInfo(tracks=[], total_tracks=0)
            
            tracks: list[Track] = []
            total_length = 0
            release_data = None

            candidate_ids = [r.get("id") for r in ranked_releases[:3] if r.get("id")]
            if candidate_ids:
                release_results = await asyncio.gather(
                    *(self._mb_repo.get_release_by_id(rid, includes=["recordings", "labels"]) for rid in candidate_ids),
                    return_exceptions=True,
                )
                failures = [r for r in release_results if isinstance(r, Exception)]
                if failures:
                    logger.warning(f"Album {release_group_id[:8]}: {len(failures)}/{len(candidate_ids)} release fetches failed")
                for result in release_results:
                    if isinstance(result, Exception) or not result:
                        continue
                    found_tracks, found_length = extract_tracks(result)
                    if found_tracks:
                        tracks = found_tracks
                        total_length = found_length
                        release_data = result
                        break
            
            if not release_data:
                return AlbumTracksInfo(tracks=[], total_tracks=0)
            
            label = extract_label(release_data)
            
            return AlbumTracksInfo(
                tracks=tracks,
                total_tracks=len(tracks),
                total_length=total_length if total_length > 0 else None,
                label=label,
                barcode=release_data.get("barcode"),
                country=release_data.get("country"),
            )
        
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to get album tracks for {release_group_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get album tracks: {e}")

    async def _fetch_release_group(self, release_group_id: str) -> dict:
        rg_result = await self._mb_repo.get_release_group_by_id(
            release_group_id,
            includes=["artists", "releases", "tags"]
        )
        
        if not rg_result:
            raise ResourceNotFoundError(f"Release group {release_group_id} not found")
        
        return rg_result

    async def _check_in_library(self, release_group_id: str, monitored_mbids: set[str] = None) -> bool:
        if monitored_mbids is not None:
            return release_group_id.lower() in monitored_mbids
        
        library_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
        return release_group_id.lower() in library_mbids
    
    def _build_basic_info(
        self,
        release_group: dict,
        release_group_id: str,
        artist_name: str,
        artist_id: str,
        in_library: bool
    ) -> AlbumInfo:
        return AlbumInfo(**build_album_basic_info(release_group, release_group_id, artist_name, artist_id, in_library))
    
    async def _enrich_with_release_details(
        self,
        album_info: AlbumInfo,
        primary_release: dict
    ) -> None:
        try:
            release_id = primary_release.get("id")
            release_data = await self._mb_repo.get_release_by_id(
                release_id,
                includes=["recordings", "labels"]
            )
            
            if not release_data:
                logger.warning(f"Release {release_id} not found")
                return
            
            tracks, total_length = extract_tracks(release_data)
            album_info.tracks = tracks
            album_info.total_tracks = len(tracks)
            album_info.total_length = total_length if total_length > 0 else None
            
            album_info.label = extract_label(release_data)
            
            album_info.barcode = release_data.get("barcode")
            album_info.country = release_data.get("country")
        
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to enrich with release details: {e}")

    async def _build_album_from_lidarr(
        self,
        release_group_id: str,
        lidarr_album: dict
    ) -> AlbumInfo:
        album_id = lidarr_album.get("id")
        
        tracks = []
        total_length = 0
        if album_id:
            lidarr_tracks = await self._lidarr_repo.get_album_tracks(album_id)
            for t in lidarr_tracks:
                duration_ms = t.get("duration_ms", 0)
                if duration_ms:
                    total_length += duration_ms
                tracks.append(Track(
                    position=int(t.get("track_number") or t.get("position", 0)),
                    disc_number=int(t.get("disc_number", 1) or 1),
                    title=t.get("title", "Unknown"),
                    length=duration_ms if duration_ms else None,
                    recording_id=None,
                ))
        
        label = None
        barcode = None
        country = None
        
        if not tracks:
            try:
                release_group = await self._fetch_release_group(release_group_id)
                ranked_releases = get_ranked_releases(release_group)
                candidate_ids = [r.get("id") for r in ranked_releases[:3] if r.get("id")]
                if candidate_ids:
                    release_results = await asyncio.gather(
                        *(self._mb_repo.get_release_by_id(rid, includes=["recordings", "labels"]) for rid in candidate_ids),
                        return_exceptions=True,
                    )
                    failures = [r for r in release_results if isinstance(r, Exception)]
                    if failures:
                        logger.warning(f"Album {release_group_id[:8]} MB fallback: {len(failures)}/{len(candidate_ids)} release fetches failed")
                    for result in release_results:
                        if isinstance(result, Exception) or not result:
                            continue
                        found_tracks, found_length = extract_tracks(result)
                        if found_tracks:
                            tracks = found_tracks
                            total_length = found_length
                            label = extract_label(result)
                            barcode = result.get("barcode")
                            country = result.get("country")
                            break
            except Exception as e:  # noqa: BLE001
                logger.warning(f"MusicBrainz fallback for tracks failed: {e}")
        
        year = None
        if release_date := lidarr_album.get("release_date"):
            try:
                year = int(release_date.split("-")[0])
            except (ValueError, IndexError):
                pass

        cover_url = prefer_release_group_cover_url(
            release_group_id,
            lidarr_album.get("cover_url"),
            size=500,
        )

        return AlbumInfo(
            title=lidarr_album.get("title", "Unknown Album"),
            musicbrainz_id=release_group_id,
            artist_name=lidarr_album.get("artist_name", "Unknown Artist"),
            artist_id=lidarr_album.get("artist_mbid", ""),
            release_date=lidarr_album.get("release_date"),
            year=year,
            type=lidarr_album.get("album_type"),
            label=label,
            barcode=barcode,
            country=country,
            disambiguation=lidarr_album.get("disambiguation"),
            tracks=tracks,
            total_tracks=len(tracks),
            total_length=total_length if total_length > 0 else None,
            in_library=True,
            cover_url=cover_url,
        )
    
    async def _build_album_from_musicbrainz(
        self,
        release_group_id: str,
        monitored_mbids: set[str] = None
    ) -> AlbumInfo:
        cached_album = await self._library_db.get_album_by_mbid(release_group_id)
        in_library = cached_album is not None
        
        release_group = await self._fetch_release_group(release_group_id)
        primary_release = find_primary_release(release_group)
        artist_name, artist_id = extract_artist_info(release_group)
        
        if not in_library:
            in_library = await self._check_in_library(release_group_id, monitored_mbids)
        
        basic_info = self._build_basic_info(
            release_group, release_group_id, artist_name, artist_id, in_library
        )
        
        if primary_release:
            await self._enrich_with_release_details(basic_info, primary_release)
        
        return basic_info

import logging
import time
from typing import Optional
from api.v1.schemas.album import AlbumInfo, AlbumBasicInfo, AlbumTracksInfo, Track
from repositories.protocols import LidarrRepositoryProtocol, MusicBrainzRepositoryProtocol
from services.preferences_service import PreferencesService
from services.album_utils import parse_year, find_primary_release, extract_artist_info, extract_tracks, extract_label, build_album_basic_info, lidarr_to_basic_info, mb_to_basic_info
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.cover_urls import prefer_release_group_cover_url
from infrastructure.validators import validate_mbid
from core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class AlbumService:
    def __init__(
        self, 
        lidarr_repo: LidarrRepositoryProtocol, 
        mb_repo: MusicBrainzRepositoryProtocol,
        library_cache: LibraryCache,
        memory_cache: CacheInterface,
        disk_cache: DiskMetadataCache,
        preferences_service: PreferencesService
    ):
        self._lidarr_repo = lidarr_repo
        self._mb_repo = mb_repo
        self._library_cache = library_cache
        self._cache = memory_cache
        self._disk_cache = disk_cache
        self._preferences_service = preferences_service
        self._revalidation_timestamps: dict[str, float] = {}

    async def is_album_cached(self, release_group_id: str) -> bool:
        cache_key = f"album_info:{release_group_id}"
        return await self._cache.get(cache_key) is not None

    async def _get_queued_mbids(self) -> set[str]:
        try:
            queue_items = await self._lidarr_repo.get_queue()
            return {item.musicbrainz_id.lower() for item in queue_items if item.musicbrainz_id}
        except Exception as e:
            logger.warning(f"Failed to fetch queue: {e}")
            return set()
    
    async def _get_cached_album_info(self, release_group_id: str, cache_key: str) -> Optional[AlbumInfo]:
        cached_info = await self._cache.get(cache_key)
        if cached_info:
            logger.info(f"Cache HIT (RAM): Album {release_group_id[:8]}... - instant load")
            return await self._revalidate_library_status(release_group_id, cached_info)
        
        logger.debug(f"Cache MISS (RAM): Album {release_group_id[:8]}...")
        
        disk_data = await self._disk_cache.get_album(release_group_id)
        if disk_data:
            logger.info(f"Cache HIT (Disk): Album {release_group_id[:8]}... - loading from persistent cache")
            album_info = AlbumInfo(**disk_data)
            album_info = await self._revalidate_library_status(release_group_id, album_info)
            advanced_settings = self._preferences_service.get_advanced_settings()
            ttl = advanced_settings.cache_ttl_album_library if album_info.in_library else advanced_settings.cache_ttl_album_non_library
            await self._cache.set(cache_key, album_info, ttl_seconds=ttl)
            return album_info
        
        logger.debug(f"Cache MISS (Disk): Album {release_group_id[:8]}...")
        return None

    async def _revalidate_library_status(self, release_group_id: str, album_info: AlbumInfo) -> AlbumInfo:
        _REVALIDATION_COOLDOWN = 60
        now = time.monotonic()
        last = self._revalidation_timestamps.get(release_group_id, 0.0)
        if now - last < _REVALIDATION_COOLDOWN:
            return album_info

        library_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
        self._revalidation_timestamps[release_group_id] = time.monotonic()
        current_in_library = release_group_id.lower() in library_mbids
        if current_in_library != album_info.in_library:
            logger.info(
                f"Library status changed for album {release_group_id[:8]}...: "
                f"{album_info.in_library} -> {current_in_library}, updating caches"
            )
            album_info.in_library = current_in_library
            await self._save_album_to_cache(release_group_id, album_info)
        return album_info

    async def _save_album_to_cache(self, release_group_id: str, album_info: AlbumInfo) -> None:
        cache_key = f"album_info:{release_group_id}"
        advanced_settings = self._preferences_service.get_advanced_settings()
        ttl = advanced_settings.cache_ttl_album_library if album_info.in_library else advanced_settings.cache_ttl_album_non_library
        await self._cache.set(cache_key, album_info, ttl_seconds=ttl)
        await self._disk_cache.set_album(release_group_id, album_info, is_monitored=album_info.in_library, ttl_seconds=ttl if not album_info.in_library else None)
        logger.info(f"Cached {'library' if album_info.in_library else 'non-library'} album {release_group_id[:8]}... for {ttl // 3600}h")

    def _check_lidarr_in_library(self, lidarr_album: dict | None) -> bool:
        if lidarr_album and lidarr_album.get("monitored", False):
            statistics = lidarr_album.get("statistics", {})
            return statistics.get("trackFileCount", 0) > 0
        return False

    async def get_album_info(self, release_group_id: str, monitored_mbids: set[str] = None) -> AlbumInfo:
        try:
            release_group_id = validate_mbid(release_group_id, "album")
        except ValueError as e:
            logger.error(f"Invalid album MBID: {e}")
            raise
        try:
            cache_key = f"album_info:{release_group_id}"
            cached = await self._get_cached_album_info(release_group_id, cache_key)
            if cached:
                return cached
            lidarr_album = await self._lidarr_repo.get_album_details(release_group_id)
            in_library = self._check_lidarr_in_library(lidarr_album)
            if in_library and lidarr_album:
                logger.info(f"Using Lidarr as primary source for album {release_group_id[:8]}")
                album_info = await self._build_album_from_lidarr(release_group_id, lidarr_album)
            else:
                logger.info(f"Using MusicBrainz as primary source for album {release_group_id[:8]}")
                album_info = await self._build_album_from_musicbrainz(release_group_id, monitored_mbids)
            await self._save_album_to_cache(release_group_id, album_info)
            return album_info
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"API call failed for album {release_group_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get album info: {e}")
    
    async def get_album_basic_info(self, release_group_id: str) -> AlbumBasicInfo:
        try:
            release_group_id = validate_mbid(release_group_id, "album")
        except ValueError as e:
            logger.error(f"Invalid album MBID: {e}")
            raise

        try:
            cache_key = f"album_info:{release_group_id}"

            requested_mbids = await self._lidarr_repo.get_requested_mbids()
            is_requested = release_group_id.lower() in requested_mbids

            cached_album_info = await self._get_cached_album_info(release_group_id, cache_key)
            if cached_album_info:
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
                    cover_url=getattr(cached_album_info, 'cover_url', None),
                )

            lidarr_album = await self._lidarr_repo.get_album_details(release_group_id)
            in_library = self._check_lidarr_in_library(lidarr_album)
            if lidarr_album and lidarr_album.get("monitored", False):
                logger.info(f"[BASIC] Using Lidarr for album {release_group_id[:8]}")
                return AlbumBasicInfo(**lidarr_to_basic_info(lidarr_album, release_group_id, in_library))
            logger.info(f"[BASIC] Using MusicBrainz for album {release_group_id[:8]}")
            release_group = await self._fetch_release_group(release_group_id)
            cached_album = await self._library_cache.get_album_by_mbid(release_group_id)
            in_library = cached_album is not None
            return AlbumBasicInfo(**mb_to_basic_info(release_group, release_group_id, in_library, is_requested))
        
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get basic album info for {release_group_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get album info: {e}")
    
    async def get_album_tracks_info(self, release_group_id: str) -> AlbumTracksInfo:
        try:
            release_group_id = validate_mbid(release_group_id, "album")
        except ValueError as e:
            logger.error(f"Invalid album MBID: {e}")
            raise
        
        try:
            cache_key = f"album_info:{release_group_id}"
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
            
            lidarr_album = await self._lidarr_repo.get_album_details(release_group_id)
            in_library = lidarr_album is not None and lidarr_album.get("monitored", False)
            
            if in_library and lidarr_album:
                logger.info(f"[TRACKS] Using Lidarr for album {release_group_id[:8]}")
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
                            position=t.get("position", 0),
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
            
            logger.info(f"[TRACKS] Using MusicBrainz for album {release_group_id[:8]}")
            release_group = await self._fetch_release_group(release_group_id)
            primary_release = find_primary_release(release_group)
            
            if not primary_release:
                return AlbumTracksInfo(tracks=[], total_tracks=0)
            
            release_id = primary_release.get("id")
            release_data = await self._mb_repo.get_release_by_id(
                release_id,
                includes=["recordings", "labels"]
            )
            
            if not release_data:
                return AlbumTracksInfo(tracks=[], total_tracks=0)
            
            tracks, total_length = extract_tracks(release_data)
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
        except Exception as e:
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
        
        except Exception as e:
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
                    position=t.get("position", 0),
                    title=t.get("title", "Unknown"),
                    length=duration_ms if duration_ms else None,
                    recording_id=None,
                ))
        
        label = None
        barcode = None
        country = None
        
        if not tracks:
            logger.debug(f"No tracks from Lidarr for album {release_group_id[:8]}, falling back to MusicBrainz")
            try:
                release_group = await self._fetch_release_group(release_group_id)
                primary_release = find_primary_release(release_group)
                if primary_release:
                    release_id = primary_release.get("id")
                    release_data = await self._mb_repo.get_release_by_id(
                        release_id,
                        includes=["recordings", "labels"]
                    )
                    if release_data:
                        tracks, total_length = extract_tracks(release_data)
                        label = extract_label(release_data)
                        barcode = release_data.get("barcode")
                        country = release_data.get("country")
            except Exception as e:
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
        cached_album = await self._library_cache.get_album_by_mbid(release_group_id)
        in_library = cached_album is not None
        
        if in_library:
            logger.info(f"Cache HIT (library DB): Album {release_group_id[:8]}... is in library")
        else:
            logger.debug(f"Cache MISS (library DB): Album {release_group_id[:8]}... not in library")
        
        logger.info(f"API CALL (MusicBrainz): Fetching album {release_group_id[:8]}...")
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
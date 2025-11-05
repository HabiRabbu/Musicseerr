import logging
from typing import Optional
from api.v1.schemas.album import AlbumInfo, Track
from repositories.lidarr_repository import LidarrRepository
from repositories.musicbrainz_repository import MusicBrainzRepository
from core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class AlbumService:
    def __init__(self, lidarr_repo: LidarrRepository, mb_repo: MusicBrainzRepository):
        self._lidarr_repo = lidarr_repo
        self._mb_repo = mb_repo
    
    @staticmethod
    def _parse_year(date_str: Optional[str]) -> Optional[int]:
        """Parse year from date string."""
        if not date_str:
            return None
        year = date_str.split("-", 1)[0]
        return int(year) if year.isdigit() else None
    
    async def get_album_info(self, release_group_id: str) -> AlbumInfo:
        """Get comprehensive album information.
        
        This is the main orchestration method - kept thin by delegating to helpers.
        """
        try:
            release_group = await self._fetch_release_group(release_group_id)
            primary_release = self._find_primary_release(release_group)
            artist_name, artist_id = self._extract_artist_info(release_group)
            in_library = await self._check_in_library(release_group_id)
            
            basic_info = self._build_basic_info(
                release_group, release_group_id, artist_name, artist_id, in_library
            )
            
            if primary_release:
                await self._enrich_with_release_details(basic_info, primary_release)
            
            return basic_info
        
        except Exception as e:
            logger.error(f"Failed to get album info for {release_group_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get album info: {e}")
    
    async def _fetch_release_group(self, release_group_id: str) -> dict:
        """Fetch release group data from MusicBrainz."""
        rg_result = await self._mb_repo.get_release_group_by_id(
            release_group_id,
            includes=["artists", "releases", "tags"]
        )
        
        if not rg_result:
            raise ResourceNotFoundError(f"Release group {release_group_id} not found")
        
        return rg_result
    
    @staticmethod
    def _find_primary_release(release_group: dict) -> Optional[dict]:
        """Find the official/primary release from the release group."""
        releases = release_group.get("release-list", [])
        
        for release in releases:
            if release.get("status") == "Official":
                return release
        
        return releases[0] if releases else None
    
    @staticmethod
    def _extract_artist_info(release_group: dict) -> tuple[str, str]:
        """Extract artist name and ID from release group."""
        artist_credit = release_group.get("artist-credit", [])
        artist_name = "Unknown Artist"
        artist_id = ""
        
        if artist_credit and isinstance(artist_credit, list):
            first_artist = artist_credit[0]
            if isinstance(first_artist, dict):
                artist_obj = first_artist.get("artist", {})
                artist_name = first_artist.get("name") or artist_obj.get("name", "Unknown Artist")
                artist_id = artist_obj.get("id", "")
        
        return artist_name, artist_id
    
    async def _check_in_library(self, release_group_id: str) -> bool:
        """Check if album is in Lidarr library."""
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
        """Build basic album info from release group data."""
        return AlbumInfo(
            title=release_group.get("title", "Unknown Album"),
            musicbrainz_id=release_group_id,
            artist_name=artist_name,
            artist_id=artist_id,
            release_date=release_group.get("first-release-date"),
            year=self._parse_year(release_group.get("first-release-date")),
            type=release_group.get("primary-type"),
            disambiguation=release_group.get("disambiguation"),
            tracks=[],
            total_tracks=0,
            in_library=in_library,
        )
    
    async def _enrich_with_release_details(
        self,
        album_info: AlbumInfo,
        primary_release: dict
    ) -> None:
        """Enrich album info with detailed release data."""
        try:
            release_id = primary_release.get("id")
            release_data = await self._mb_repo.get_release_by_id(
                release_id,
                includes=["recordings", "labels"]
            )
            
            if not release_data:
                logger.warning(f"Release {release_id} not found")
                return
            
            tracks, total_length = self._extract_tracks(release_data)
            album_info.tracks = tracks
            album_info.total_tracks = len(tracks)
            album_info.total_length = total_length if total_length > 0 else None
            
            album_info.label = self._extract_label(release_data)
            
            album_info.barcode = release_data.get("barcode")
            album_info.country = release_data.get("country")
        
        except Exception as e:
            logger.error(f"Failed to enrich with release details: {e}")
    
    @staticmethod
    def _extract_tracks(release_data: dict) -> tuple[list[Track], int]:
        """Extract tracks and total length from release data."""
        tracks = []
        total_length = 0
        
        medium_list = release_data.get("medium-list", [])
        for medium in medium_list:
            track_list = medium.get("track-list", [])
            for track in track_list:
                recording = track.get("recording", {})
                length_ms = recording.get("length")
                
                if length_ms:
                    try:
                        total_length += int(length_ms)
                    except (ValueError, TypeError):
                        pass
                
                tracks.append(
                    Track(
                        position=int(track.get("position", 0)),
                        title=recording.get("title", "Unknown"),
                        length=int(length_ms) if length_ms else None,
                        recording_id=recording.get("id"),
                    )
                )
        
        return tracks, total_length
    
    @staticmethod
    def _extract_label(release_data: dict) -> Optional[str]:
        """Extract label name from release data."""
        label_info_list = release_data.get("label-info-list", [])
        if label_info_list:
            label_obj = label_info_list[0].get("label")
            if label_obj:
                return label_obj.get("name")
        return None

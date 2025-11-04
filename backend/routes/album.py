"""Album routes for fetching album details."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
import musicbrainzngs

from models import AlbumInfo, Track
from utils.cache import cached
from utils import lidarr

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/album", tags=["album"])


def _parse_year(date_str: Optional[str]) -> Optional[int]:
    """Extract year from ISO date string."""
    if not date_str:
        return None
    year = date_str.split("-", 1)[0]
    return int(year) if year.isdigit() else None


def _format_track_length(length_ms: Optional[int]) -> Optional[int]:
    """Format track length from milliseconds."""
    return length_ms if length_ms else None


@cached(ttl_seconds=3600, key_prefix="album:")
async def _fetch_album_details(release_group_id: str) -> dict:
    """Fetch album details from MusicBrainz with caching."""
    try:
        rg_result = musicbrainzngs.get_release_group_by_id(
            release_group_id,
            includes=["artists", "releases", "tags"]
        )
        release_group = rg_result.get("release-group", {})
        
        releases = release_group.get("release-list", [])
        primary_release = None
        
        for release in releases:
            if release.get("status") == "Official":
                primary_release = release
                break
        
        if not primary_release and releases:
            primary_release = releases[0]
        
        tracks = []
        total_length = 0
        label = None
        barcode = None
        country = None
        
        if primary_release:
            release_id = primary_release.get("id")
            if release_id:
                release_result = musicbrainzngs.get_release_by_id(
                    release_id,
                    includes=["recordings", "labels", "artist-credits"]
                )
                release = release_result.get("release", {})
                
                label_info_list = release.get("label-info-list", [])
                if label_info_list:
                    label_obj = label_info_list[0].get("label", {})
                    label = label_obj.get("name")
                
                barcode = release.get("barcode")
                country = release.get("country")
                
                medium_list = release.get("medium-list", [])
                track_position = 1
                for medium in medium_list:
                    track_list = medium.get("track-list", [])
                    for track in track_list:
                        recording = track.get("recording", {})
                        length = recording.get("length")
                        
                        if length:
                            total_length += int(length)
                        
                        tracks.append(Track(
                            position=track_position,
                            title=recording.get("title", "Unknown Track"),
                            length=int(length) if length else None,
                            recording_id=recording.get("id")
                        ))
                        track_position += 1
        
        artist_credit = release_group.get("artist-credit", [])
        artist_name = "Unknown Artist"
        artist_id = ""
        
        if artist_credit and len(artist_credit) > 0:
            first_credit = artist_credit[0]
            if isinstance(first_credit, dict):
                artist_obj = first_credit.get("artist", {})
                artist_name = artist_obj.get("name", artist_name)
                artist_id = artist_obj.get("id", "")
        
        return {
            "title": release_group.get("title", "Unknown Album"),
            "musicbrainz_id": release_group_id,
            "artist_name": artist_name,
            "artist_id": artist_id,
            "release_date": release_group.get("first-release-date"),
            "year": _parse_year(release_group.get("first-release-date")),
            "type": release_group.get("type"),
            "label": label,
            "barcode": barcode,
            "country": country,
            "disambiguation": release_group.get("disambiguation"),
            "tracks": [track.model_dump() for track in tracks],
            "total_tracks": len(tracks),
            "total_length": total_length if total_length > 0 else None,
        }
    except Exception as e:
        logger.error(f"Error fetching album {release_group_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch album details: {str(e)}")


@router.get("/{release_group_id}", response_model=AlbumInfo)
async def get_album(release_group_id: str):
    """Get detailed information about an album."""
    album_data = await _fetch_album_details(release_group_id)
    
    library_mbids = await lidarr.get_library_mbids(include_release_ids=True)
    in_library = release_group_id.lower() in library_mbids
    album_data["in_library"] = in_library
    
    return AlbumInfo(**album_data)

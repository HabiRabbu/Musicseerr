from typing import Optional
from pydantic import BaseModel, Field


class Track(BaseModel):
    position: int
    title: str
    length: Optional[int] = None
    recording_id: Optional[str] = None


class AlbumInfo(BaseModel):
    title: str
    musicbrainz_id: str
    artist_name: str
    artist_id: str
    release_date: Optional[str] = None
    year: Optional[int] = None
    type: Optional[str] = None
    label: Optional[str] = None
    barcode: Optional[str] = None
    country: Optional[str] = None
    disambiguation: Optional[str] = None
    tracks: list[Track] = Field(default_factory=list)
    total_tracks: int = 0
    total_length: Optional[int] = None
    in_library: bool = False
    requested: bool = False
    cover_url: Optional[str] = None


class AlbumBasicInfo(BaseModel):
    """Minimal album info for fast initial load - no tracks."""
    title: str
    musicbrainz_id: str
    artist_name: str
    artist_id: str
    release_date: Optional[str] = None
    year: Optional[int] = None
    type: Optional[str] = None
    disambiguation: Optional[str] = None
    in_library: bool = False
    requested: bool = False
    cover_url: Optional[str] = None


class AlbumTracksInfo(BaseModel):
    """Track list and extended details - loaded asynchronously."""
    tracks: list[Track] = Field(default_factory=list)
    total_tracks: int = 0
    total_length: Optional[int] = None
    label: Optional[str] = None
    barcode: Optional[str] = None
    country: Optional[str] = None

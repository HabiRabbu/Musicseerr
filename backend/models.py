"""Data models for Musicseerr API."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A search result for an artist or album."""
    type: Literal["artist", "album"]
    title: str
    artist: Optional[str] = None
    year: Optional[int] = None
    musicbrainz_id: str
    in_library: bool = False
    cover_url: Optional[str] = None


class AlbumRequest(BaseModel):
    """Request to add an album to library."""
    musicbrainz_id: str
    artist: Optional[str] = Field(None, description="Artist name (optional)")
    album: Optional[str] = Field(None, description="Album title (optional)")
    year: Optional[int] = None


class LibraryAlbum(BaseModel):
    """An album in the Lidarr library."""
    artist: str
    album: str
    year: Optional[int] = None
    monitored: bool
    quality: Optional[str] = None
    cover_url: Optional[str] = None
    musicbrainz_id: Optional[str] = Field(None, alias="foreignAlbumId")

    class Config:
        populate_by_name = True


class QueueItem(BaseModel):
    """An item in the download queue."""
    artist: str
    album: str
    status: str
    progress: Optional[int] = Field(None, ge=0, le=100)
    eta: Optional[datetime] = None
    musicbrainz_id: Optional[str] = None


class ServiceStatus(BaseModel):
    """Status of an external service."""
    status: Literal["ok", "error"]
    version: Optional[str] = None
    message: Optional[str] = None


class StatusReport(BaseModel):
    """Overall system status report."""
    status: Literal["ok", "degraded", "error"]
    services: dict[str, ServiceStatus]


class ExternalLink(BaseModel):
    """External link for an artist."""
    type: str
    url: str
    label: str


class ArtistInfo(BaseModel):
    """Detailed artist information."""
    name: str
    musicbrainz_id: str
    disambiguation: Optional[str] = None
    type: Optional[str] = None
    country: Optional[str] = None
    life_span: Optional[dict[str, Optional[str]]] = None
    description: Optional[str] = None
    image: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    external_links: list[ExternalLink] = Field(default_factory=list)
    in_library: bool = False
    albums: list[dict] = Field(default_factory=list)
    singles: list[dict] = Field(default_factory=list)
    eps: list[dict] = Field(default_factory=list)


class UserPreferences(BaseModel):
    """User preferences for filtering releases."""
    primary_types: list[str] = Field(
        default=["album", "ep", "single"],
        description="Included primary release types"
    )
    secondary_types: list[str] = Field(
        default=["studio"],
        description="Included secondary release types"
    )
    release_statuses: list[str] = Field(
        default=["official"],
        description="Included release statuses"
    )


class Track(BaseModel):
    """A track in an album."""
    position: int
    title: str
    length: Optional[int] = None  # Length in milliseconds
    recording_id: Optional[str] = None


class AlbumInfo(BaseModel):
    """Detailed album information."""
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
    total_length: Optional[int] = None  # Total length in milliseconds
    in_library: bool = False

from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Unified model for search results (artist or album)."""

    type: Literal["artist", "album"]
    title: str
    artist: Optional[str] = None
    year: Optional[int] = None
    musicbrainz_id: str
    in_library: bool = False
    cover_url: Optional[str] = None


class AlbumRequest(BaseModel):
    """Incoming request body for /api/request."""

    musicbrainz_id: str
    artist: Optional[str] = Field(None, description="Optional; not required for the request flow")
    album: Optional[str]  = Field(None, description="Optional; not required for the request flow")
    year: Optional[int] = None


class LibraryAlbum(BaseModel):
    """
    Simplified representation of a Lidarr library album.
    Normalized to expose the MusicBrainz ID as "musicbrainz_id",
    even though Lidarr provides it as "foreignAlbumId".
    """

    artist: str
    album: str
    year: Optional[int] = None
    monitored: bool
    quality: Optional[str] = None
    cover_url: Optional[str] = None

    musicbrainz_id: Optional[str] = Field(None, alias="foreignAlbumId")

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True
        fields = {"musicbrainz_id": {"alias": "foreignAlbumId"}}

    @property
    def foreignAlbumId(self) -> Optional[str]:
        """Backward alias for external API compatibility."""
        return self.musicbrainz_id


class QueueItem(BaseModel):
    """Normalized download/import queue item."""

    artist: str
    album: str
    status: str
    progress: Optional[int] = None
    eta: Optional[datetime] = None
    musicbrainz_id: Optional[str] = None



class ServiceStatus(BaseModel):
    """Status report for one dependency."""

    status: Literal["ok", "error"]
    version: Optional[str] = None
    message: Optional[str] = None


class StatusReport(BaseModel):
    """Overall service health."""

    status: Literal["ok", "degraded", "error"]
    services: Dict[str, ServiceStatus]


class ConfigInfo(BaseModel):
    """Safe configuration snapshot for frontend."""

    lidarr_url: str
    quality_profile_id: int
    root_folder_id: int

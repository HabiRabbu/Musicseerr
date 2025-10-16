from datetime import datetime
from typing import Literal, Optional, Dict
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    type: Literal["artist", "album"]
    title: str
    artist: Optional[str] = None
    year: Optional[int] = None
    musicbrainz_id: str
    in_library: bool = False
    cover_url: Optional[str] = None


class AlbumRequest(BaseModel):
    musicbrainz_id: str
    artist: Optional[str] = Field(None, description="Optional")
    album: Optional[str] = Field(None, description="Optional")
    year: Optional[int] = None


class LibraryAlbum(BaseModel):
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
        return self.musicbrainz_id


class QueueItem(BaseModel):
    artist: str
    album: str
    status: str
    progress: Optional[int] = None
    eta: Optional[datetime] = None
    musicbrainz_id: Optional[str] = None


class ServiceStatus(BaseModel):
    status: Literal["ok", "error"]
    version: Optional[str] = None
    message: Optional[str] = None


class StatusReport(BaseModel):
    status: Literal["ok", "degraded", "error"]
    services: Dict[str, ServiceStatus]


class ConfigInfo(BaseModel):
    lidarr_url: str
    quality_profile_id: int
    root_folder_id: int

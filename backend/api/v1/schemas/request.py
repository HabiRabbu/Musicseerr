from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AlbumRequest(BaseModel):
    musicbrainz_id: str
    artist: Optional[str] = Field(None, description="Artist name (optional)")
    album: Optional[str] = Field(None, description="Album title (optional)")
    year: Optional[int] = None


class RequestResponse(BaseModel):
    success: bool
    message: str
    lidarr_response: Optional[dict] = None


class QueueItem(BaseModel):
    artist: str
    album: str
    status: str
    progress: Optional[int] = Field(None, ge=0, le=100)
    eta: Optional[datetime] = None
    musicbrainz_id: Optional[str] = None


class QueueStatusResponse(BaseModel):
    queue_size: int
    processing: bool

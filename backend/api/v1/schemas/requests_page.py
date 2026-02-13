from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class StatusMessage(BaseModel):
    title: Optional[str] = None
    messages: list[str] = Field(default_factory=list)


class ActiveRequestItem(BaseModel):
    musicbrainz_id: str
    artist_name: str
    album_title: str
    artist_mbid: Optional[str] = None
    year: Optional[int] = None
    cover_url: Optional[str] = None
    requested_at: datetime
    status: str
    progress: Optional[float] = None
    eta: Optional[datetime] = None
    size: Optional[float] = None
    size_remaining: Optional[float] = None
    download_status: Optional[str] = None
    download_state: Optional[str] = None
    status_messages: Optional[list[StatusMessage]] = None
    error_message: Optional[str] = None
    lidarr_queue_id: Optional[int] = None


class RequestHistoryItem(BaseModel):
    musicbrainz_id: str
    artist_name: str
    album_title: str
    artist_mbid: Optional[str] = None
    year: Optional[int] = None
    cover_url: Optional[str] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    in_library: bool = False


class ActiveRequestsResponse(BaseModel):
    items: list[ActiveRequestItem]
    count: int


class RequestHistoryResponse(BaseModel):
    items: list[RequestHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CancelRequestResponse(BaseModel):
    success: bool
    message: str


class RetryRequestResponse(BaseModel):
    success: bool
    message: str


class ClearHistoryResponse(BaseModel):
    success: bool


class ActiveCountResponse(BaseModel):
    count: int

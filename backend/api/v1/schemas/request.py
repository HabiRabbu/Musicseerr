from models.request import QueueItem as QueueItem
from infrastructure.msgspec_fastapi import AppStruct


class AlbumRequest(AppStruct):
    musicbrainz_id: str
    artist: str | None = None
    album: str | None = None
    year: int | None = None


class RequestAcceptedResponse(AppStruct):
    success: bool
    message: str
    musicbrainz_id: str
    status: str = "pending"


class QueueStatusResponse(AppStruct):
    queue_size: int
    processing: bool
    active_workers: int = 0
    max_workers: int = 1

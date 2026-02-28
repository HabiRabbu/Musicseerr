from datetime import datetime
from typing import Annotated

import msgspec

from infrastructure.msgspec_fastapi import AppStruct


class AlbumRequest(AppStruct):
    musicbrainz_id: str
    artist: str | None = None
    album: str | None = None
    year: int | None = None


class RequestResponse(AppStruct):
    success: bool
    message: str
    lidarr_response: dict | None = None


class QueueItem(AppStruct):
    artist: str
    album: str
    status: str
    progress: Annotated[int, msgspec.Meta(ge=0, le=100)] | None = None
    eta: datetime | None = None
    musicbrainz_id: str | None = None


class QueueStatusResponse(AppStruct):
    queue_size: int
    processing: bool

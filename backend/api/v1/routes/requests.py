import logging
from fastapi import APIRouter, Depends
from api.v1.schemas.request import AlbumRequest, RequestResponse, QueueStatusResponse
from core.dependencies import get_request_service
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.request_service import RequestService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/api/requests", tags=["requests"])


@router.post("/new", response_model=RequestResponse)
async def request_album(
    album_request: AlbumRequest = MsgSpecBody(AlbumRequest),
    request_service: RequestService = Depends(get_request_service)
):
    return await request_service.request_album(
        album_request.musicbrainz_id,
        artist=album_request.artist,
        album=album_request.album,
        year=album_request.year,
    )


@router.get("/new/queue-status", response_model=QueueStatusResponse)
async def get_queue_status(
    request_service: RequestService = Depends(get_request_service)
):
    return request_service.get_queue_status()

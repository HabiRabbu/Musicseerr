from fastapi import APIRouter, Depends
from api.v1.schemas.request import AlbumRequest, RequestAcceptedResponse, QueueStatusResponse
from core.dependencies import get_request_service
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.request_service import RequestService

router = APIRouter(route_class=MsgSpecRoute, prefix="/requests", tags=["requests"])


@router.post("/new", response_model=RequestAcceptedResponse, status_code=202)
async def request_album(
    album_request: AlbumRequest = MsgSpecBody(AlbumRequest),
    request_service: RequestService = Depends(get_request_service),
):
    return await request_service.request_album(
        album_request.musicbrainz_id,
        artist=album_request.artist,
        album=album_request.album,
        year=album_request.year,
        artist_mbid=album_request.artist_mbid,
        monitor_artist=album_request.monitor_artist,
        auto_download_artist=album_request.auto_download_artist,
    )


@router.get("/new/queue-status", response_model=QueueStatusResponse)
async def get_queue_status(
    request_service: RequestService = Depends(get_request_service)
):
    return request_service.get_queue_status()

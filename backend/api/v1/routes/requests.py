import logging
from fastapi import APIRouter, Depends
from api.v1.schemas.request import AlbumRequest, RequestResponse, QueueStatusResponse
from core.dependencies import get_request_service
from services.request_service import RequestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/request", tags=["requests"])


@router.post("", response_model=RequestResponse)
async def request_album(
    album_request: AlbumRequest,
    request_service: RequestService = Depends(get_request_service)
):
    result = await request_service.request_album(album_request.musicbrainz_id)
    return RequestResponse(**result)


@router.get("/queue-status", response_model=QueueStatusResponse)
async def get_queue_status(
    request_service: RequestService = Depends(get_request_service)
):
    return request_service.get_queue_status()

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from api.v1.schemas.requests_page import (
    ActiveCountResponse,
    ActiveRequestsResponse,
    CancelRequestResponse,
    ClearHistoryResponse,
    RequestHistoryResponse,
    RetryRequestResponse,
)
from core.dependencies import get_requests_page_service
from infrastructure.validators import validate_mbid
from services.requests_page_service import RequestsPageService

router = APIRouter(prefix="/api/requests", tags=["requests-page"])


@router.get("/active", response_model=ActiveRequestsResponse)
async def get_active_requests(
    service: RequestsPageService = Depends(get_requests_page_service),
):
    return await service.get_active_requests()


@router.get("/active/count", response_model=ActiveCountResponse)
async def get_active_request_count(
    service: RequestsPageService = Depends(get_requests_page_service),
):
    count = await service.get_active_count()
    return ActiveCountResponse(count=count)


@router.get("/history", response_model=RequestHistoryResponse)
async def get_request_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    service: RequestsPageService = Depends(get_requests_page_service),
):
    return await service.get_request_history(
        page=page, page_size=page_size, status_filter=status
    )


@router.delete("/active/{musicbrainz_id}", response_model=CancelRequestResponse)
async def cancel_request(
    musicbrainz_id: str,
    service: RequestsPageService = Depends(get_requests_page_service),
):
    try:
        musicbrainz_id = validate_mbid(musicbrainz_id, "album")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await service.cancel_request(musicbrainz_id)


@router.post("/retry/{musicbrainz_id}", response_model=RetryRequestResponse)
async def retry_request(
    musicbrainz_id: str,
    service: RequestsPageService = Depends(get_requests_page_service),
):
    try:
        musicbrainz_id = validate_mbid(musicbrainz_id, "album")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await service.retry_request(musicbrainz_id)


@router.delete("/history/{musicbrainz_id}", response_model=ClearHistoryResponse)
async def clear_history_item(
    musicbrainz_id: str,
    service: RequestsPageService = Depends(get_requests_page_service),
):
    try:
        musicbrainz_id = validate_mbid(musicbrainz_id, "album")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    deleted = await service.clear_history_item(musicbrainz_id)
    return ClearHistoryResponse(success=deleted)

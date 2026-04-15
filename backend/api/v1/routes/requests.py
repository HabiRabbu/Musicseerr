from fastapi import APIRouter, Depends, HTTPException, Request
from api.v1.schemas.request import AlbumRequest, RequestAcceptedResponse, QueueStatusResponse
from core.dependencies import get_request_service, get_request_history_store, get_auth_service
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from infrastructure.persistence.request_history import RequestHistoryStore
from services.auth_service import AuthService
from services.request_service import RequestService

router = APIRouter(route_class=MsgSpecRoute, prefix="/requests", tags=["requests"])


@router.post("/new", response_model=RequestAcceptedResponse, status_code=202)
async def request_album(
    http_request: Request,
    album_request: AlbumRequest = MsgSpecBody(AlbumRequest),
    request_service: RequestService = Depends(get_request_service),
    request_history: RequestHistoryStore = Depends(get_request_history_store),
    auth: AuthService = Depends(get_auth_service),
):
    current_user = getattr(http_request.state, "current_user", None)
    username: str | None = current_user["username"] if current_user else None
    role: str = current_user["role"] if current_user else "admin"

    if auth.is_auth_enabled() and username and role != "admin":
        can_request, quota, quota_days = auth.get_effective_request_settings(username)
        if not can_request:
            raise HTTPException(status_code=403, detail="You don't have permission to make requests")
        if quota is not None:
            used = await request_history.async_count_user_requests(username, quota_days)
            if used >= quota:
                raise HTTPException(
                    status_code=429,
                    detail=f"Request quota reached ({used}/{quota} in the last {quota_days} days)",
                )

    return await request_service.request_album(
        album_request.musicbrainz_id,
        artist=album_request.artist,
        album=album_request.album,
        year=album_request.year,
        artist_mbid=album_request.artist_mbid,
        monitor_artist=album_request.monitor_artist,
        auto_download_artist=album_request.auto_download_artist,
        requested_by=username,
    )


@router.get("/new/queue-status", response_model=QueueStatusResponse)
async def get_queue_status(
    request_service: RequestService = Depends(get_request_service)
):
    return request_service.get_queue_status()

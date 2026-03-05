import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from api.v1.schemas.stream import (
    JellyfinPlaybackUrlResponse,
    PlaybackSessionResponse,
    ProgressReportRequest,
    StartPlaybackRequest,
    StopReportRequest,
)
from core.dependencies import (
    get_jellyfin_repository,
    get_jellyfin_playback_service,
    get_local_files_service,
)
from core.exceptions import ExternalServiceError, PlaybackNotAllowedError, ResourceNotFoundError
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from repositories.jellyfin_repository import JellyfinRepository
from services.jellyfin_playback_service import JellyfinPlaybackService
from services.local_files_service import LocalFilesService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/api/stream", tags=["streaming"])


@router.get("/jellyfin/{item_id}")
async def stream_jellyfin_audio(
    item_id: str,
    jellyfin_repo: JellyfinRepository = Depends(get_jellyfin_repository),
) -> JellyfinPlaybackUrlResponse:
    try:
        playback = await jellyfin_repo.get_playback_url(item_id)
        logger.info(
            "Resolved Jellyfin playback metadata",
            extra={
                "item_id": item_id,
                "play_method": playback.play_method,
                "seekable": playback.seekable,
            },
        )
        return JellyfinPlaybackUrlResponse(
            url=playback.url,
            seekable=playback.seekable,
            playSessionId=playback.play_session_id,
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Audio item not found")
    except PlaybackNotAllowedError as e:
        logger.warning("Playback not allowed for %s: %s", item_id, e)
        raise HTTPException(status_code=403, detail=str(e))
    except ExternalServiceError as e:
        logger.error("Jellyfin stream error for %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Failed to stream from Jellyfin")


@router.head("/jellyfin/{item_id}")
async def head_jellyfin_audio(
    item_id: str,
    jellyfin_repo: JellyfinRepository = Depends(get_jellyfin_repository),
) -> Response:
    try:
        playback = await jellyfin_repo.get_playback_url(item_id)
        logger.info(
            "Resolved Jellyfin playback prefetch redirect",
            extra={
                "item_id": item_id,
                "play_method": playback.play_method,
                "seekable": playback.seekable,
            },
        )
        return RedirectResponse(
            url=playback.url,
            status_code=302,
            headers={"Referrer-Policy": "no-referrer"},
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Audio item not found")
    except PlaybackNotAllowedError as e:
        logger.warning("Playback not allowed for %s: %s", item_id, e)
        raise HTTPException(status_code=403, detail=str(e))
    except ExternalServiceError as e:
        logger.error("Jellyfin head stream error for %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Failed to resolve Jellyfin stream")


@router.post("/jellyfin/{item_id}/start", response_model=PlaybackSessionResponse)
async def start_jellyfin_playback(
    item_id: str,
    body: StartPlaybackRequest | None = Body(default=None),
    playback_service: JellyfinPlaybackService = Depends(get_jellyfin_playback_service),
) -> PlaybackSessionResponse:
    try:
        play_session_id = await playback_service.start_playback(
            item_id,
            play_session_id=body.play_session_id if body else None,
        )
        return PlaybackSessionResponse(play_session_id=play_session_id, item_id=item_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    except PlaybackNotAllowedError as e:
        logger.warning("Playback not allowed for %s: %s", item_id, e)
        raise HTTPException(status_code=403, detail=str(e))
    except ExternalServiceError as e:
        logger.error("Failed to start playback for %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Failed to start Jellyfin playback")


@router.post("/jellyfin/{item_id}/progress", status_code=204)
async def report_jellyfin_progress(
    item_id: str,
    body: ProgressReportRequest = MsgSpecBody(ProgressReportRequest),
    playback_service: JellyfinPlaybackService = Depends(get_jellyfin_playback_service),
) -> Response:
    try:
        await playback_service.report_progress(
            item_id=item_id,
            play_session_id=body.play_session_id,
            position_seconds=body.position_seconds,
            is_paused=body.is_paused,
        )
        return Response(status_code=204)
    except ExternalServiceError as e:
        logger.warning("Progress report failed for %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Failed to report progress")


@router.post("/jellyfin/{item_id}/stop", status_code=204)
async def stop_jellyfin_playback(
    item_id: str,
    body: StopReportRequest = MsgSpecBody(StopReportRequest),
    playback_service: JellyfinPlaybackService = Depends(get_jellyfin_playback_service),
) -> Response:
    try:
        await playback_service.stop_playback(
            item_id=item_id,
            play_session_id=body.play_session_id,
            position_seconds=body.position_seconds,
        )
        return Response(status_code=204)
    except ExternalServiceError as e:
        logger.warning("Stop report failed for %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Failed to report playback stop")


@router.get("/local/{track_id}")
async def stream_local_file(
    track_id: int,
    request: Request,
    local_service: LocalFilesService = Depends(get_local_files_service),
) -> StreamingResponse:
    try:
        range_header = request.headers.get("Range")
        chunks, headers, status_code = await local_service.stream_track(
            track_file_id=track_id,
            range_header=range_header,
        )
        return StreamingResponse(
            content=chunks,
            status_code=status_code,
            headers=headers,
            media_type=headers.get("Content-Type", "application/octet-stream"),
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Track file not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Track file not found on disk")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied — path outside music directory")
    except ExternalServiceError as e:
        detail = str(e)
        if "Range not satisfiable" in detail:
            raise HTTPException(status_code=416, detail=detail)
        logger.error("Local stream error for track %s: %s", track_id, e)
        raise HTTPException(status_code=502, detail="Failed to stream local file")
    except OSError as e:
        logger.error("OS error streaming local track %s: %s", track_id, e)
        raise HTTPException(status_code=500, detail="Failed to read local file")

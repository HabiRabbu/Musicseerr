import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response

from api.v1.schemas.stream import PlaybackSessionResponse, ProgressReportRequest, StopReportRequest
from core.dependencies import (
    get_stream_service,
    get_jellyfin_playback_service,
    get_local_files_service,
)
from core.exceptions import ExternalServiceError, PlaybackNotAllowedError, ResourceNotFoundError
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.stream_service import StreamService
from services.jellyfin_playback_service import JellyfinPlaybackService
from services.local_files_service import LocalFilesService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/api/stream", tags=["streaming"])


@router.get("/jellyfin/{item_id}")
async def stream_jellyfin_audio(
    item_id: str,
    request: Request,
    codec: Literal["aac", "mp3", "opus", "flac", "vorbis", "alac", "wav", "wma"] = Query(default="aac", alias="format"),
    bitrate: int = Query(default=128000, ge=32000, le=320000),
    stream_service: StreamService = Depends(get_stream_service),
) -> StreamingResponse:
    try:
        range_header = request.headers.get("Range")
        chunks, headers, status_code = await stream_service.stream_jellyfin_audio(
            item_id=item_id,
            audio_codec=codec,
            bitrate=bitrate,
            range_header=range_header,
        )
        return StreamingResponse(
            content=chunks,
            status_code=status_code,
            headers=headers,
            media_type=headers.get("Content-Type", "audio/aac"),
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Audio item not found")
    except ExternalServiceError as e:
        logger.error("Jellyfin stream error for %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Failed to stream from Jellyfin")


@router.post("/jellyfin/{item_id}/start", response_model=PlaybackSessionResponse)
async def start_jellyfin_playback(
    item_id: str,
    playback_service: JellyfinPlaybackService = Depends(get_jellyfin_playback_service),
) -> PlaybackSessionResponse:
    try:
        play_session_id = await playback_service.start_playback(item_id)
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

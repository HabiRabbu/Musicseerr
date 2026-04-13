import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import msgspec

from api.v1.schemas.cache_status import CacheSyncStatus
from core.dependencies import get_cache_status_service
from infrastructure.msgspec_fastapi import MsgSpecRoute
from services.cache_status_service import CacheStatusService

router = APIRouter(route_class=MsgSpecRoute, prefix="/cache/sync", tags=["cache"])


@router.get("/status", response_model=CacheSyncStatus)
async def get_sync_status(
    status_service: CacheStatusService = Depends(get_cache_status_service),
):
    progress = status_service.get_progress()

    return CacheSyncStatus(
        is_syncing=progress.is_syncing,
        phase=progress.phase,
        total_items=progress.total_items,
        processed_items=progress.processed_items,
        progress_percent=progress.progress_percent,
        current_item=progress.current_item,
        started_at=progress.started_at,
        error_message=progress.error_message,
        total_artists=progress.total_artists,
        processed_artists=progress.processed_artists,
        total_albums=progress.total_albums,
        processed_albums=progress.processed_albums
    )


@router.post("/cancel")
async def cancel_sync(
    status_service: CacheStatusService = Depends(get_cache_status_service),
):
    from core.task_registry import TaskRegistry
    await status_service.cancel_current_sync()
    TaskRegistry.get_instance().cancel("precache-library")
    await status_service.wait_for_completion()
    return {"status": "cancelled"}


@router.get("/stream")
async def stream_sync_status(
    status_service: CacheStatusService = Depends(get_cache_status_service),
):
    queue = status_service.subscribe_sse()

    async def event_generator():
        try:
            progress = status_service.get_progress()
            initial_data = {
                'is_syncing': progress.is_syncing,
                'phase': progress.phase,
                'total_items': progress.total_items,
                'processed_items': progress.processed_items,
                'progress_percent': progress.progress_percent,
                'current_item': progress.current_item,
                'started_at': progress.started_at,
                'error_message': progress.error_message,
                'total_artists': progress.total_artists,
                'processed_artists': progress.processed_artists,
                'total_albums': progress.total_albums,
                'processed_albums': progress.processed_albums
            }
            yield f"data: {msgspec.json.encode(initial_data).decode('utf-8')}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            status_service.unsubscribe_sse(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

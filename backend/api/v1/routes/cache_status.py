import logging
from fastapi import APIRouter

from api.v1.schemas.cache_status import CacheSyncStatus
from services.cache_status_service import CacheStatusService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache/sync", tags=["cache"])


@router.get("/status", response_model=CacheSyncStatus)
async def get_sync_status():
    status_service = CacheStatusService()
    progress = status_service.get_progress()
    
    return CacheSyncStatus(
        is_syncing=progress.is_syncing,
        phase=progress.phase,
        total_items=progress.total_items,
        processed_items=progress.processed_items,
        progress_percent=progress.progress_percent,
        current_item=progress.current_item,
        started_at=progress.started_at
    )

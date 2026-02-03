import logging
from fastapi import APIRouter, Depends, HTTPException
from api.v1.schemas.request import QueueItem
from core.dependencies import get_lidarr_repository
from repositories.lidarr import LidarrRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.get("", response_model=list[QueueItem])
async def get_queue(
    lidarr_repo: LidarrRepository = Depends(get_lidarr_repository)
):
    try:
        return await lidarr_repo.get_queue()
    except Exception as e:
        logger.error(f"Failed to get queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to load queue")

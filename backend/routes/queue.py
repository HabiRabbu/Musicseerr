from fastapi import APIRouter, HTTPException
from utils.common import ApiError
from utils import lidarr

router = APIRouter(prefix="/api/queue", tags=["queue"])

@router.get("")
async def get_queue():
    """Get the current download queue from Lidarr."""
    try:
        queue = await lidarr.get_queue()
        return {"queue": queue or []}
    except ApiError as e:
        raise HTTPException(status_code=400, detail=e.message or "Failed to fetch queue")

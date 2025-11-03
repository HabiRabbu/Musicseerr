"""Album request endpoints."""
from fastapi import APIRouter, HTTPException

from models import AlbumRequest
from utils.common import ApiError
from utils import request_queue

router = APIRouter(prefix="/api/request", tags=["requests"])


@router.post("")
async def request_album(album_request: AlbumRequest):
    """Request an album to be added to Lidarr library."""
    try:
        result = await request_queue.add_to_queue(album_request.musicbrainz_id)
        return {
            "success": True,
            "message": result["message"],
            "lidarr_response": result["payload"]
        }
    except ApiError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/queue-status")
async def get_queue_status():
    """Get current request queue status."""
    return request_queue.get_queue_status()

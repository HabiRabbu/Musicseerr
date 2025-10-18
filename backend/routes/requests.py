from fastapi import APIRouter, HTTPException
from utils.common import ApiError
from models import AlbumRequest
from utils import request_queue

router = APIRouter(prefix="/api/request")


@router.post("", response_model=dict)
async def request(album_request: AlbumRequest):
    try:
        result = await request_queue.add_to_queue(album_request.musicbrainz_id)
        return {"success": True, "message": result["message"], "lidarr_response": result["payload"]}
    except ApiError as e:
        raise HTTPException(status_code=400, detail=e.message or "Request failed")


@router.get("/queue-status", response_model=dict)
async def get_queue_status():
    return request_queue.get_queue_status()

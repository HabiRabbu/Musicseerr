from fastapi import APIRouter, HTTPException
from utils.common import ApiError
from models import AlbumRequest
from utils import lidarr

router = APIRouter(prefix="/api/request")


@router.post("", response_model=dict)
async def request(album_request: AlbumRequest):
    try:
        result = await lidarr.add_album(album_request.musicbrainz_id)
        return {"success": True, "message": result["message"], "lidarr_response": result["payload"]}
    except ApiError as e:
        raise HTTPException(status_code=400, detail=e.message or "Request failed")

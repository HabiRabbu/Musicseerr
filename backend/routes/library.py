from fastapi import APIRouter, HTTPException
from utils.common import ApiError
from utils import lidarr

router = APIRouter(prefix="/api/library", tags=["library"])

@router.get("/")
async def get_library():
    try:
        library = await lidarr.get_library()
        return {"library": library or []}
    except ApiError as e:
        raise HTTPException(status_code=400, detail=e.message or "Failed to fetch library")
    
@router.get("/artists")
async def get_library_grouped():
    """Return library grouped by artist."""
    try:
        grouped = await lidarr.get_library_grouped()
        return {"library": grouped or []}
    except ApiError as e:
        raise HTTPException(status_code=400, detail=e.message or "Failed to fetch grouped library")

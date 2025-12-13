import logging
from fastapi import APIRouter, Depends, HTTPException, status
from api.v1.schemas.album import AlbumInfo, AlbumBasicInfo, AlbumTracksInfo
from core.dependencies import get_album_service
from services.album_service import AlbumService
from infrastructure.validators import is_unknown_mbid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/album", tags=["album"])


@router.get("/{album_id}", response_model=AlbumInfo)
async def get_album(
    album_id: str,
    album_service: AlbumService = Depends(get_album_service)
):
    if is_unknown_mbid(album_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown album ID: {album_id}"
        )
    
    try:
        return await album_service.get_album_info(album_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{album_id}/basic", response_model=AlbumBasicInfo)
async def get_album_basic(
    album_id: str,
    album_service: AlbumService = Depends(get_album_service)
):
    """Get minimal album info for fast initial load - no tracks."""
    if is_unknown_mbid(album_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown album ID: {album_id}"
        )
    
    try:
        return await album_service.get_album_basic_info(album_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{album_id}/tracks", response_model=AlbumTracksInfo)
async def get_album_tracks(
    album_id: str,
    album_service: AlbumService = Depends(get_album_service)
):
    """Get track list and extended details - loaded asynchronously."""
    if is_unknown_mbid(album_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown album ID: {album_id}"
        )
    
    try:
        return await album_service.get_album_tracks_info(album_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

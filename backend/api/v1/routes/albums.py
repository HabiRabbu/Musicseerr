import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.v1.schemas.album import AlbumInfo, AlbumBasicInfo, AlbumTracksInfo
from api.v1.schemas.discovery import SimilarAlbumsResponse, MoreByArtistResponse
from core.dependencies import get_album_service, get_album_discovery_service
from services.album_service import AlbumService
from services.album_discovery_service import AlbumDiscoveryService
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


@router.get("/{album_id}/similar", response_model=SimilarAlbumsResponse)
async def get_similar_albums(
    album_id: str,
    artist_id: str = Query(..., description="Artist MBID for similarity lookup"),
    count: int = Query(default=10, ge=1, le=30),
    discovery_service: AlbumDiscoveryService = Depends(get_album_discovery_service)
):
    """Get albums from similar artists."""
    if is_unknown_mbid(album_id) or is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unknown album/artist ID"
        )
    return await discovery_service.get_similar_albums(album_id, artist_id, count)


@router.get("/{album_id}/more-by-artist", response_model=MoreByArtistResponse)
async def get_more_by_artist(
    album_id: str,
    artist_id: str = Query(..., description="Artist MBID"),
    count: int = Query(default=10, ge=1, le=30),
    discovery_service: AlbumDiscoveryService = Depends(get_album_discovery_service)
):
    """Get other albums by the same artist."""
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unknown artist ID"
        )
    return await discovery_service.get_more_by_artist(artist_id, album_id, count)

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.v1.schemas.artist import ArtistInfo, ArtistExtendedInfo, ArtistReleases
from core.dependencies import get_artist_service
from services.artist_service import ArtistService
from infrastructure.validators import is_unknown_mbid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/artist", tags=["artist"])


@router.get("/{artist_id}", response_model=ArtistInfo)
async def get_artist(
    artist_id: str,
    artist_service: ArtistService = Depends(get_artist_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    
    try:
        return await artist_service.get_artist_info_basic(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{artist_id}/extended", response_model=ArtistExtendedInfo)
async def get_artist_extended(
    artist_id: str,
    artist_service: ArtistService = Depends(get_artist_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    
    try:
        return await artist_service.get_artist_extended_info(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{artist_id}/releases", response_model=ArtistReleases)
async def get_artist_releases(
    artist_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    artist_service: ArtistService = Depends(get_artist_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    
    try:
        return await artist_service.get_artist_releases(artist_id, offset, limit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

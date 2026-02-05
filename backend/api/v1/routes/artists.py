import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.v1.schemas.artist import ArtistInfo, ArtistExtendedInfo, ArtistReleases
from api.v1.schemas.discovery import SimilarArtistsResponse, TopSongsResponse, TopAlbumsResponse
from core.dependencies import get_artist_service, get_artist_discovery_service
from services.artist_service import ArtistService
from services.artist_discovery_service import ArtistDiscoveryService
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


@router.get("/{artist_id}/similar", response_model=SimilarArtistsResponse)
async def get_similar_artists(
    artist_id: str,
    count: int = Query(default=15, ge=1, le=50),
    discovery_service: ArtistDiscoveryService = Depends(get_artist_discovery_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    return await discovery_service.get_similar_artists(artist_id, count)


@router.get("/{artist_id}/top-songs", response_model=TopSongsResponse)
async def get_top_songs(
    artist_id: str,
    count: int = Query(default=10, ge=1, le=50),
    discovery_service: ArtistDiscoveryService = Depends(get_artist_discovery_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    return await discovery_service.get_top_songs(artist_id, count)


@router.get("/{artist_id}/top-albums", response_model=TopAlbumsResponse)
async def get_top_albums(
    artist_id: str,
    count: int = Query(default=10, ge=1, le=50),
    discovery_service: ArtistDiscoveryService = Depends(get_artist_discovery_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    return await discovery_service.get_top_albums(artist_id, count)

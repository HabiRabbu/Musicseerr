import logging
from fastapi import APIRouter, Depends, Query
from api.v1.schemas.home import (
    HomeResponse,
    GenreDetailResponse,
    TrendingArtistsResponse,
    TrendingArtistsRangeResponse,
    PopularAlbumsResponse,
    PopularAlbumsRangeResponse,
)
from core.dependencies import get_home_service
from services.home_service import HomeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("", response_model=HomeResponse)
async def get_home_data(
    home_service: HomeService = Depends(get_home_service)
):
    return await home_service.get_home_data()


@router.get("/genre/{genre_name}", response_model=GenreDetailResponse)
async def get_genre_detail(
    genre_name: str,
    limit: int = Query(default=50, ge=1, le=200),
    artist_offset: int = Query(default=0, ge=0),
    album_offset: int = Query(default=0, ge=0),
    home_service: HomeService = Depends(get_home_service)
):
    return await home_service.get_genre_artists(
        genre=genre_name,
        limit=limit,
        artist_offset=artist_offset,
        album_offset=album_offset,
    )


@router.get("/trending/artists", response_model=TrendingArtistsResponse)
async def get_trending_artists(
    limit: int = Query(default=10, ge=1, le=25),
    home_service: HomeService = Depends(get_home_service)
):
    return await home_service.get_trending_artists(limit=limit)


@router.get("/trending/artists/{range_key}", response_model=TrendingArtistsRangeResponse)
async def get_trending_artists_by_range(
    range_key: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    home_service: HomeService = Depends(get_home_service)
):
    return await home_service.get_trending_artists_by_range(
        range_key=range_key, limit=limit, offset=offset
    )


@router.get("/popular/albums", response_model=PopularAlbumsResponse)
async def get_popular_albums(
    limit: int = Query(default=10, ge=1, le=25),
    home_service: HomeService = Depends(get_home_service)
):
    return await home_service.get_popular_albums(limit=limit)


@router.get("/popular/albums/{range_key}", response_model=PopularAlbumsRangeResponse)
async def get_popular_albums_by_range(
    range_key: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    home_service: HomeService = Depends(get_home_service)
):
    return await home_service.get_popular_albums_by_range(
        range_key=range_key, limit=limit, offset=offset
    )


@router.get("/genre-artist/{genre_name}")
async def get_genre_artist(
    genre_name: str,
    home_service: HomeService = Depends(get_home_service)
):
    artist_mbid = await home_service.get_genre_artist(genre_name)
    return {"artist_mbid": artist_mbid}


@router.post("/genre-artists")
async def get_genre_artists_batch(
    genres: list[str],
    home_service: HomeService = Depends(get_home_service)
):
    """Batch fetch artist MBIDs for multiple genres in a single request."""
    results = await home_service.get_genre_artists_batch(genres)
    return {"genre_artists": results}

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from api.v1.schemas.plex import (
    PlexAlbumDetail,
    PlexAlbumMatch,
    PlexAlbumPage,
    PlexAlbumSummary,
    PlexArtistSummary,
    PlexLibraryStats,
    PlexSearchResponse,
)
from core.dependencies import get_plex_library_service, get_plex_repository
from core.exceptions import ExternalServiceError
from infrastructure.msgspec_fastapi import MsgSpecRoute
from repositories.plex_repository import PlexRepository
from services.plex_library_service import PlexLibraryService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/plex", tags=["plex-library"])

_PLEX_SORT_FIELD: dict[str, str] = {
    "name": "titleSort",
    "date_added": "addedAt",
    "year": "year",
}


@router.get("/albums", response_model=PlexAlbumPage)
async def get_plex_albums(
    limit: int = Query(default=48, ge=1, le=500, alias="limit"),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default=""),
    genre: str = Query(default=""),
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> PlexAlbumPage:
    field = _PLEX_SORT_FIELD.get(sort_by, "titleSort")
    direction = "desc" if sort_order == "desc" else "asc"
    plex_sort = f"{field}:{direction}"
    try:
        items, total_from_plex = await service.get_albums(
            size=limit, offset=offset, sort=plex_sort,
            genre=genre if genre else None,
        )
    except ExternalServiceError as e:
        logger.error("Plex service error getting albums: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Plex")

    return PlexAlbumPage(items=items, total=total_from_plex)


@router.get("/albums/{rating_key}", response_model=PlexAlbumDetail)
async def get_plex_album_detail(
    rating_key: str,
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> PlexAlbumDetail:
    result = await service.get_album_detail(rating_key)
    if not result:
        raise HTTPException(status_code=404, detail="Album not found")
    return result


@router.get("/artists", response_model=list[PlexArtistSummary])
async def get_plex_artists(
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> list[PlexArtistSummary]:
    try:
        return await service.get_artists()
    except ExternalServiceError as e:
        logger.error("Plex service error getting artists: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Plex")


@router.get("/search", response_model=PlexSearchResponse)
async def search_plex(
    q: str = Query(..., min_length=1),
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> PlexSearchResponse:
    try:
        return await service.search(q)
    except ExternalServiceError as e:
        logger.error("Plex service error searching: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Plex")


@router.get("/recent", response_model=list[PlexAlbumSummary])
async def get_plex_recent(
    limit: int = Query(default=20, ge=1, le=50),
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> list[PlexAlbumSummary]:
    try:
        return await service.get_recent(limit=limit)
    except ExternalServiceError as e:
        logger.error("Plex service error getting recent: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Plex")


@router.get("/genres", response_model=list[str])
async def get_plex_genres(
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> list[str]:
    try:
        return await service.get_genres()
    except ExternalServiceError as e:
        logger.error("Plex service error getting genres: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Plex")


@router.get("/stats", response_model=PlexLibraryStats)
async def get_plex_stats(
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> PlexLibraryStats:
    try:
        return await service.get_stats()
    except ExternalServiceError as e:
        logger.error("Plex service error getting stats: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Plex")


@router.get("/thumb/{rating_key}")
async def get_plex_thumb(
    rating_key: str,
    size: int = Query(default=500, ge=32, le=1200),
    repo: PlexRepository = Depends(get_plex_repository),
) -> Response:
    try:
        image_bytes, content_type = await repo.proxy_thumb(rating_key, size)
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except ExternalServiceError as e:
        logger.warning("Plex thumb failed for %s: %s", rating_key, e)
        raise HTTPException(status_code=502, detail="Failed to fetch thumbnail")


@router.get("/album-match/{album_id}", response_model=PlexAlbumMatch)
async def match_plex_album(
    album_id: str,
    name: str = Query(default=""),
    artist: str = Query(default=""),
    service: PlexLibraryService = Depends(get_plex_library_service),
) -> PlexAlbumMatch:
    try:
        return await service.get_album_match(
            album_id=album_id, album_name=name, artist_name=artist,
        )
    except ExternalServiceError as e:
        logger.error("Failed to match Plex album %s: %s", album_id, e)
        raise HTTPException(status_code=502, detail="Failed to match Plex album")

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from api.v1.schemas.navidrome import (
    NavidromeAlbumDetail,
    NavidromeAlbumMatch,
    NavidromeAlbumPage,
    NavidromeAlbumSummary,
    NavidromeArtistSummary,
    NavidromeLibraryStats,
    NavidromeSearchResponse,
)
from core.dependencies import get_navidrome_library_service, get_navidrome_repository
from core.exceptions import ExternalServiceError
from infrastructure.msgspec_fastapi import MsgSpecRoute
from repositories.navidrome_repository import NavidromeRepository
from services.navidrome_library_service import NavidromeLibraryService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/navidrome", tags=["navidrome-library"])


_SORT_MAP: dict[str, str] = {
    "name": "alphabeticalByName",
    "date_added": "newest",
    "year": "alphabeticalByName",
}


@router.get("/albums", response_model=NavidromeAlbumPage)
async def get_navidrome_albums(
    limit: int = Query(default=48, ge=1, le=500, alias="limit"),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="name"),
    genre: str = Query(default=""),
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> NavidromeAlbumPage:
    subsonic_type = "byGenre" if genre else _SORT_MAP.get(sort_by, "alphabeticalByName")
    try:
        items = await service.get_albums(
            type=subsonic_type, size=limit, offset=offset, genre=genre if genre else None,
        )
    except ExternalServiceError as e:
        logger.error("Navidrome service error getting albums: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Navidrome")

    try:
        stats = await service.get_stats()
        total = stats.total_albums if len(items) >= limit else offset + len(items)
    except ExternalServiceError:
        logger.warning("Navidrome stats unavailable, using heuristic pagination total")
        total = offset + len(items) + (1 if len(items) >= limit else 0)

    return NavidromeAlbumPage(items=items, total=total)


@router.get("/albums/{album_id}", response_model=NavidromeAlbumDetail)
async def get_navidrome_album_detail(
    album_id: str,
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> NavidromeAlbumDetail:
    result = await service.get_album_detail(album_id)
    if not result:
        raise HTTPException(status_code=404, detail="Album not found")
    return result


@router.get("/artists", response_model=list[NavidromeArtistSummary])
async def get_navidrome_artists(
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> list[NavidromeArtistSummary]:
    return await service.get_artists()


@router.get("/artists/{artist_id}")
async def get_navidrome_artist_detail(
    artist_id: str,
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> dict:
    result = await service.get_artist_detail(artist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Artist not found")
    return result


@router.get("/search", response_model=NavidromeSearchResponse)
async def search_navidrome(
    q: str = Query(..., min_length=1),
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> NavidromeSearchResponse:
    return await service.search(q)


@router.get("/recent", response_model=list[NavidromeAlbumSummary])
async def get_navidrome_recent(
    limit: int = Query(default=20, ge=1, le=50),
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> list[NavidromeAlbumSummary]:
    return await service.get_recent(limit=limit)


@router.get("/favorites", response_model=list[NavidromeAlbumSummary])
async def get_navidrome_favorites(
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> list[NavidromeAlbumSummary]:
    result = await service.get_favorites()
    return result.albums


@router.get("/genres", response_model=list[str])
async def get_navidrome_genres(
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> list[str]:
    try:
        return await service.get_genres()
    except ExternalServiceError as e:
        logger.error("Navidrome service error getting genres: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Navidrome")


@router.get("/stats", response_model=NavidromeLibraryStats)
async def get_navidrome_stats(
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> NavidromeLibraryStats:
    return await service.get_stats()


@router.get("/cover/{cover_art_id}")
async def get_navidrome_cover(
    cover_art_id: str,
    size: int = Query(default=500, ge=32, le=1200),
    repo: NavidromeRepository = Depends(get_navidrome_repository),
) -> Response:
    try:
        image_bytes, content_type = await repo.get_cover_art(cover_art_id, size)
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except ExternalServiceError as e:
        logger.warning("Navidrome cover art failed for %s: %s", cover_art_id, e)
        raise HTTPException(status_code=502, detail="Failed to fetch cover art")


@router.get("/album-match/{album_id}", response_model=NavidromeAlbumMatch)
async def match_navidrome_album(
    album_id: str,
    name: str = Query(default=""),
    artist: str = Query(default=""),
    service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> NavidromeAlbumMatch:
    try:
        return await service.get_album_match(
            album_id=album_id, album_name=name, artist_name=artist,
        )
    except ExternalServiceError as e:
        logger.error("Failed to match Navidrome album %s: %s", album_id, e)
        raise HTTPException(status_code=502, detail="Failed to match Navidrome album")

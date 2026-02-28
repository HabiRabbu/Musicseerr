import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.v1.schemas.jellyfin import (
    JellyfinAlbumDetail,
    JellyfinAlbumMatch,
    JellyfinAlbumSummary,
    JellyfinArtistSummary,
    JellyfinLibraryStats,
    JellyfinPaginatedResponse,
    JellyfinSearchResponse,
    JellyfinTrackInfo,
)
from core.dependencies import get_jellyfin_library_service
from core.exceptions import ExternalServiceError
from infrastructure.msgspec_fastapi import MsgSpecRoute
from services.jellyfin_library_service import JellyfinLibraryService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/api/jellyfin", tags=["jellyfin-library"])


@router.get("/albums", response_model=JellyfinPaginatedResponse)
async def get_jellyfin_albums(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["SortName", "DateCreated", "PlayCount", "ProductionYear"] = Query(default="SortName"),
    sort_order: Literal["Ascending", "Descending"] = Query(default="Ascending"),
    genre: str | None = Query(default=None),
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> JellyfinPaginatedResponse:
    try:
        items, total = await service.get_albums(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, genre=genre
        )
        return JellyfinPaginatedResponse(
            items=items, total=total, offset=offset, limit=limit
        )
    except ExternalServiceError as e:
        logger.error("Jellyfin service error getting albums: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Jellyfin")
    except Exception as e:
        logger.error("Failed to get Jellyfin albums: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get Jellyfin albums")


@router.get("/albums/{album_id}", response_model=JellyfinAlbumDetail)
async def get_jellyfin_album_detail(
    album_id: str,
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> JellyfinAlbumDetail:
    try:
        result = await service.get_album_detail(album_id)
        if not result:
            raise HTTPException(status_code=404, detail="Album not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get Jellyfin album %s: %s", album_id, e)
        raise HTTPException(status_code=500, detail="Failed to get Jellyfin album")


@router.get(
    "/albums/{album_id}/tracks", response_model=list[JellyfinTrackInfo]
)
async def get_jellyfin_album_tracks(
    album_id: str,
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> list[JellyfinTrackInfo]:
    try:
        return await service.get_album_tracks(album_id)
    except ExternalServiceError as e:
        logger.error("Jellyfin service error getting album tracks %s: %s", album_id, e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Jellyfin")
    except Exception as e:
        logger.error("Failed to get Jellyfin album tracks %s: %s", album_id, e)
        raise HTTPException(status_code=500, detail="Failed to get album tracks")


@router.get(
    "/albums/match/{musicbrainz_id}", response_model=JellyfinAlbumMatch
)
async def match_jellyfin_album(
    musicbrainz_id: str,
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> JellyfinAlbumMatch:
    try:
        return await service.match_album_by_mbid(musicbrainz_id)
    except ExternalServiceError as e:
        logger.error("Failed to match Jellyfin album %s: %s", musicbrainz_id, e)
        raise HTTPException(status_code=502, detail="Failed to match Jellyfin album")


@router.get("/artists", response_model=list[JellyfinArtistSummary])
async def get_jellyfin_artists(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> list[JellyfinArtistSummary]:
    try:
        return await service.get_artists(limit=limit, offset=offset)
    except Exception as e:
        logger.error("Failed to get Jellyfin artists: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get Jellyfin artists")


@router.get("/search", response_model=JellyfinSearchResponse)
async def search_jellyfin(
    q: str = Query(..., min_length=1),
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> JellyfinSearchResponse:
    try:
        return await service.search(q)
    except Exception as e:
        logger.error("Jellyfin search failed for '%s': %s", q, e)
        raise HTTPException(status_code=500, detail="Jellyfin search failed")


@router.get("/recent", response_model=list[JellyfinAlbumSummary])
async def get_jellyfin_recent(
    limit: int = Query(default=20, ge=1, le=50),
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> list[JellyfinAlbumSummary]:
    try:
        return await service.get_recently_played(limit=limit)
    except Exception as e:
        logger.error("Failed to get Jellyfin recent: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get recently played")


@router.get("/favorites", response_model=list[JellyfinAlbumSummary])
async def get_jellyfin_favorites(
    limit: int = Query(default=20, ge=1, le=50),
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> list[JellyfinAlbumSummary]:
    try:
        return await service.get_favorites(limit=limit)
    except Exception as e:
        logger.error("Failed to get Jellyfin favorites: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get favorites")


@router.get("/genres", response_model=list[str])
async def get_jellyfin_genres(
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> list[str]:
    try:
        return await service.get_genres()
    except ExternalServiceError as e:
        logger.error("Jellyfin service error getting genres: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with Jellyfin")
    except Exception as e:
        logger.error("Failed to get Jellyfin genres: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get genres")


@router.get("/stats", response_model=JellyfinLibraryStats)
async def get_jellyfin_stats(
    service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
) -> JellyfinLibraryStats:
    try:
        return await service.get_stats()
    except Exception as e:
        logger.error("Failed to get Jellyfin stats: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get library stats")

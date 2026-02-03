import logging
from fastapi import APIRouter, Depends, HTTPException
from api.v1.schemas.library import (
    LibraryResponse,
    LibraryArtistsResponse,
    LibraryAlbumsResponse,
    RecentlyAddedResponse,
    LibraryStatsResponse
)
from core.dependencies import get_library_service
from core.exceptions import ExternalServiceError
from services.library_service import LibraryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/", response_model=LibraryResponse)
async def get_library(
    library_service: LibraryService = Depends(get_library_service)
):
    library = await library_service.get_library()
    return LibraryResponse(library=library)


@router.get("/artists", response_model=LibraryArtistsResponse)
async def get_library_artists(
    limit: int | None = None,
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        artists = await library_service.get_artists(limit=limit)
        return LibraryArtistsResponse(artists=artists, total=len(artists))
    except Exception as e:
        logger.error(f"Failed to get library artists: {e}")
        raise HTTPException(status_code=500, detail="Failed to load artists")


@router.get("/albums", response_model=LibraryAlbumsResponse)
async def get_library_albums(
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        albums = await library_service.get_library()
        return LibraryAlbumsResponse(albums=albums, total=len(albums))
    except Exception as e:
        logger.error(f"Failed to get library albums: {e}")
        raise HTTPException(status_code=500, detail="Failed to load albums")


@router.get("/recently-added", response_model=RecentlyAddedResponse)
async def get_recently_added(
    limit: int = 20,
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        albums = await library_service.get_recently_added(limit=limit)
        return RecentlyAddedResponse(albums=albums, artists=[])
    except Exception as e:
        logger.error(f"Failed to get recently added: {e}")
        raise HTTPException(status_code=500, detail="Failed to load recently added")


@router.post("/sync")
async def sync_library(
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        return await library_service.sync_library(is_manual=True)
    except ExternalServiceError as e:
        logger.error(f"Failed to sync library: {e}")
        if "cooldown" in str(e).lower():
            raise HTTPException(status_code=429, detail="Sync is on cooldown, please wait")
        raise HTTPException(status_code=503, detail="External service unavailable")
    except Exception as e:
        logger.error(f"Failed to sync library: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync library")


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_library_stats(
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        return await library_service.get_stats()
    except Exception as e:
        logger.error(f"Failed to get library stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to load stats")


@router.get("/mbids")
async def get_library_mbids(
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        mbids = await library_service.get_library_mbids()
        return {"mbids": mbids}
    except Exception as e:
        logger.error(f"Failed to get library mbids: {e}")
        raise HTTPException(status_code=500, detail="Failed to load library")


@router.get("/grouped")
async def get_library_grouped(
    library_service: LibraryService = Depends(get_library_service)
):
    grouped = await library_service.get_library_grouped()
    return {"library": grouped}

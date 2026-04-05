import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from api.v1.schemas.library import (
    LibraryResponse,
    LibraryArtistsResponse,
    LibraryAlbumsResponse,
    PaginatedLibraryAlbumsResponse,
    PaginatedLibraryArtistsResponse,
    RecentlyAddedResponse,
    LibraryStatsResponse,
    AlbumRemoveResponse,
    AlbumRemovePreviewResponse,
    SyncLibraryResponse,
    LibraryMbidsResponse,
    LibraryGroupedResponse,
    TrackResolveRequest,
    TrackResolveResponse,
)
from core.dependencies import get_library_service
from core.exceptions import ExternalServiceError
from infrastructure.msgspec_fastapi import MsgSpecRoute, MsgSpecBody
from services.library_service import LibraryService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/library", tags=["library"])


@router.get("/", response_model=LibraryResponse)
async def get_library(
    library_service: LibraryService = Depends(get_library_service)
):
    library = await library_service.get_library()
    return LibraryResponse(library=library)


@router.get("/artists", response_model=PaginatedLibraryArtistsResponse)
async def get_library_artists(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "name",
    sort_order: str = "asc",
    q: str | None = None,
    library_service: LibraryService = Depends(get_library_service)
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    allowed_sort = {"name", "album_count", "date_added"}
    if sort_by not in allowed_sort:
        sort_by = "name"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    artists, total = await library_service.get_artists_paginated(
        limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=q,
    )
    return PaginatedLibraryArtistsResponse(artists=artists, total=total, offset=offset, limit=limit)


@router.get("/albums", response_model=PaginatedLibraryAlbumsResponse)
async def get_library_albums(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "date_added",
    sort_order: str = "desc",
    q: str | None = None,
    library_service: LibraryService = Depends(get_library_service)
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    allowed_sort = {"date_added", "artist", "title", "year"}
    if sort_by not in allowed_sort:
        sort_by = "date_added"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    albums, total = await library_service.get_albums_paginated(
        limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, search=q,
    )
    return PaginatedLibraryAlbumsResponse(albums=albums, total=total, offset=offset, limit=limit)


@router.get("/recently-added", response_model=RecentlyAddedResponse)
async def get_recently_added(
    limit: int = 20,
    library_service: LibraryService = Depends(get_library_service)
):
    albums = await library_service.get_recently_added(limit=limit)
    return RecentlyAddedResponse(albums=albums, artists=[])


@router.post("/sync", response_model=SyncLibraryResponse)
async def sync_library(
    force_full: bool = Query(default=False, description="Clear resume checkpoint and start a full sync from scratch"),
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        return await library_service.sync_library(is_manual=True, force_full=force_full)
    except ExternalServiceError as e:
        if "cooldown" in str(e).lower():
            raise HTTPException(status_code=429, detail="Sync is on cooldown, please wait")
        raise


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_library_stats(
    library_service: LibraryService = Depends(get_library_service)
):
    return await library_service.get_stats()


@router.get("/mbids", response_model=LibraryMbidsResponse)
async def get_library_mbids(
    library_service: LibraryService = Depends(get_library_service)
):
    mbids, requested = await asyncio.gather(
        library_service.get_library_mbids(),
        library_service.get_requested_mbids(),
    )
    return LibraryMbidsResponse(mbids=mbids, requested_mbids=requested)


@router.get("/grouped", response_model=LibraryGroupedResponse)
async def get_library_grouped(
    library_service: LibraryService = Depends(get_library_service)
):
    grouped = await library_service.get_library_grouped()
    return LibraryGroupedResponse(library=grouped)


@router.get("/album/{album_mbid}/removal-preview", response_model=AlbumRemovePreviewResponse)
async def get_album_removal_preview(
    album_mbid: str,
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        return await library_service.get_album_removal_preview(album_mbid)
    except ExternalServiceError as e:
        logger.error(f"Failed to get album removal preview: {e}")
        raise HTTPException(status_code=500, detail="Failed to load removal preview")


@router.delete("/album/{album_mbid}", response_model=AlbumRemoveResponse)
async def remove_album(
    album_mbid: str,
    delete_files: bool = False,
    library_service: LibraryService = Depends(get_library_service)
):
    try:
        return await library_service.remove_album(album_mbid, delete_files=delete_files)
    except ExternalServiceError as e:
        logger.error(f"Couldn't remove album {album_mbid}: {e}")
        raise HTTPException(status_code=500, detail="Couldn't remove this album")


@router.post("/resolve-tracks", response_model=TrackResolveResponse)
async def resolve_tracks(
    body: TrackResolveRequest = MsgSpecBody(TrackResolveRequest),
    library_service: LibraryService = Depends(get_library_service),
):
    return await library_service.resolve_tracks_batch(body.items)

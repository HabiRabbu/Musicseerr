"""Search endpoints for artists and albums."""
import asyncio
import logging

from fastapi import APIRouter, Query, Path, BackgroundTasks

from utils import musicbrainz, lidarr, coverart

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


async def _safe_gather(*tasks):
    """Gather tasks, replacing exceptions with default values."""
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if not isinstance(r, Exception) else None for r in results]


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search term"),
    limit_per_bucket: int | None = Query(
        None, ge=1, le=100,
        description="Max items per bucket (deprecated, use limit_artists/limit_albums)"
    ),
    limit_artists: int = Query(10, ge=1, le=100, description="Max artists to return"),
    limit_albums: int = Query(10, ge=1, le=100, description="Max albums to return"),
    buckets: str | None = Query(
        None, description="Comma-separated subset: artists,albums"
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Search for artists and albums across MusicBrainz."""
    buckets_list = [b.strip().lower() for b in buckets.split(",")] if buckets else None
    
    # Determine limits
    limits = {}
    if not buckets_list or "artists" in buckets_list:
        limits["artists"] = limit_per_bucket if limit_per_bucket else limit_artists
    if not buckets_list or "albums" in buckets_list:
        limits["albums"] = limit_per_bucket if limit_per_bucket else limit_albums
    
    # Parallel searches
    grouped, library_mbids = await _safe_gather(
        musicbrainz.search_musicbrainz_grouped(q, limits=limits, buckets=buckets_list),
        lidarr.get_library_mbids(include_release_ids=True),
    )
    
    grouped = grouped or {"artists": [], "albums": []}
    library_mbids = library_mbids or set()
    
    # Mark albums in library
    for item in grouped.get("albums", []):
        item.in_library = (item.musicbrainz_id or "").lower() in library_mbids
    
    # Prefetch cover art for first 12 albums
    for item in grouped.get("albums", [])[:12]:
        if item.musicbrainz_id:
            background_tasks.add_task(
                coverart.get_release_group_cover,
                item.musicbrainz_id,
                "250"
            )
    
    return grouped


@router.get("/{bucket}")
async def search_bucket(
    bucket: str = Path(..., pattern="^(artists|albums)$"),
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Search a specific bucket (artists or albums) with pagination."""
    results, library_mbids = await _safe_gather(
        musicbrainz.search_musicbrainz_bucket(q, bucket=bucket, limit=limit, offset=offset),
        lidarr.get_library_mbids(include_release_ids=True),
    )
    
    results = results or []
    library_mbids = library_mbids or set()
    
    # Mark albums in library
    if bucket == "albums":
        for item in results:
            item.in_library = (item.musicbrainz_id or "").lower() in library_mbids
    
    return {"bucket": bucket, "limit": limit, "offset": offset, "results": results}
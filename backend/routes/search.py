import asyncio
from fastapi import APIRouter, Query, Path, BackgroundTasks
from utils import musicbrainz, lidarr, coverart

router = APIRouter(prefix="/api/search")


@router.get("", response_model=dict)
async def search(
    q: str = Query(..., min_length=1, description="Search term"),
    limit_per_bucket: int | None = Query(None, ge=1, le=100, description="Max items per bucket (deprecated, use limit_artists/limit_albums)"),
    limit_artists: int = Query(10, ge=1, le=100, description="Max artists to return"),
    limit_albums: int = Query(10, ge=1, le=100, description="Max albums to return"),
    buckets: str | None = Query(
        None, description="Comma-separated subset of buckets: artists,albums"
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    buckets_list = [b.strip().lower() for b in buckets.split(",")] if buckets else None
    
    limits = {}
    if not buckets_list or "artists" in buckets_list:
        limits["artists"] = limit_per_bucket if limit_per_bucket is not None else limit_artists
    if not buckets_list or "albums" in buckets_list:
        limits["albums"] = limit_per_bucket if limit_per_bucket is not None else limit_albums

    mb_task = asyncio.create_task(
        musicbrainz.search_musicbrainz_grouped(
            q, limits=limits, buckets=buckets_list
        )
    )
    lib_task = asyncio.create_task(lidarr.get_library_mbids(include_release_ids=True))

    try:
        grouped, library_mbids = await asyncio.gather(mb_task, lib_task, return_exceptions=True)
        
        if isinstance(grouped, Exception):
            grouped = {"artists": [], "albums": []}
        if isinstance(library_mbids, Exception):
            library_mbids = set()
    except Exception:
        try:
            grouped = await mb_task
        except Exception:
            grouped = {"artists": [], "albums": []}
        library_mbids = set()

    lib = library_mbids or set()

    for item in grouped.get("albums", []):
        item.in_library = (item.musicbrainz_id or "").lower() in lib

    for item in grouped.get("albums", [])[:12]:
        if item.musicbrainz_id:
            background_tasks.add_task(
                coverart.get_release_group_cover, 
                item.musicbrainz_id, 
                "250"
            )

    return grouped


@router.get("/{bucket}", response_model=dict)
async def search_bucket(
    bucket: str = Path(..., pattern="^(artists|albums)$"),
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=100, description="Page size (max 100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    mb_task = asyncio.create_task(
        musicbrainz.search_musicbrainz_bucket(q, bucket=bucket, limit=limit, offset=offset)
    )
    lib_task = asyncio.create_task(lidarr.get_library_mbids(include_release_ids=True))

    try:
        results, library_mbids = await asyncio.gather(mb_task, lib_task, return_exceptions=True)
        
        if isinstance(results, Exception):
            results = []
        if isinstance(library_mbids, Exception):
            library_mbids = set()
    except Exception:
        try:
            results = await mb_task
        except Exception:
            results = []
        library_mbids = set()

    lib = library_mbids or set()
    
    if bucket == "albums":
        for r in results:
            r.in_library = (r.musicbrainz_id or "").lower() in lib

    return {"bucket": bucket, "limit": limit, "offset": offset, "results": results}


import logging
from fastapi import APIRouter, Query, Path, BackgroundTasks, Depends
from api.v1.schemas.search import SearchResponse
from core.dependencies import get_search_service, get_coverart_repository
from services.search_service import SearchService
from repositories.coverart_repository import CoverArtRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1, description="Search term"),
    limit_per_bucket: int | None = Query(
        None, ge=1, le=100,
        description="Max items per bucket (deprecated, use limit_artists/limit_albums)"
    ),
    limit_artists: int = Query(10, ge=0, le=100, description="Max artists to return"),
    limit_albums: int = Query(10, ge=0, le=100, description="Max albums to return"),
    buckets: str | None = Query(
        None, description="Comma-separated subset: artists,albums"
    ),
    search_service: SearchService = Depends(get_search_service),
    coverart_repo: CoverArtRepository = Depends(get_coverart_repository)
):
    buckets_list = [b.strip().lower() for b in buckets.split(",")] if buckets else None
    
    final_limit_artists = limit_per_bucket if limit_per_bucket else limit_artists
    final_limit_albums = limit_per_bucket if limit_per_bucket else limit_albums
    
    result = await search_service.search(
        query=q,
        limit_artists=final_limit_artists,
        limit_albums=final_limit_albums,
        buckets=buckets_list
    )
    
    album_ids = search_service.schedule_cover_prefetch(result.albums)
    if album_ids:
        background_tasks.add_task(
            coverart_repo.batch_prefetch_covers,
            album_ids,
            "250"
        )
    
    return result


@router.get("/{bucket}")
async def search_bucket(
    bucket: str = Path(..., pattern="^(artists|albums)$"),
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    search_service: SearchService = Depends(get_search_service)
):
    results = await search_service.search_bucket(
        bucket=bucket,
        query=q,
        limit=limit,
        offset=offset
    )
    return {"bucket": bucket, "limit": limit, "offset": offset, "results": results}


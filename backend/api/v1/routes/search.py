from fastapi import APIRouter, Query, Path, BackgroundTasks, Depends, Request
from core.exceptions import ClientDisconnectedError
from api.v1.schemas.search import (
    SearchResponse,
    SearchBucketResponse,
    EnrichmentResponse,
    EnrichmentBatchRequest,
    SuggestResponse,
)
from core.dependencies import get_search_service, get_coverart_repository, get_search_enrichment_service
from infrastructure.degradation import try_get_degradation_context
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute

import msgspec.structs
from services.search_service import SearchService
from services.search_enrichment_service import SearchEnrichmentService
from repositories.coverart_repository import CoverArtRepository

router = APIRouter(route_class=MsgSpecRoute, prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    request: Request,
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
    if await request.is_disconnected():
        raise ClientDisconnectedError("Client disconnected")
    
    buckets_list = [b.strip().lower() for b in buckets.split(",")] if buckets else None
    
    final_limit_artists = limit_per_bucket if limit_per_bucket else limit_artists
    final_limit_albums = limit_per_bucket if limit_per_bucket else limit_albums
    
    result = await search_service.search(
        query=q,
        limit_artists=final_limit_artists,
        limit_albums=final_limit_albums,
        buckets=buckets_list
    )
    
    ctx = try_get_degradation_context()
    if ctx is not None and ctx.has_degradation():
        result = msgspec.structs.replace(result, service_status=ctx.degraded_summary())
    
    album_ids = search_service.schedule_cover_prefetch(result.albums)
    if album_ids:
        background_tasks.add_task(
            coverart_repo.batch_prefetch_covers,
            album_ids,
            "250"
        )
    
    return result


@router.get("/suggest", response_model=SuggestResponse)
async def suggest(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(5, ge=1, le=10, description="Max results"),
    search_service: SearchService = Depends(get_search_service),
) -> SuggestResponse:
    stripped = q.strip()
    if len(stripped) < 2:
        return SuggestResponse()
    return await search_service.suggest(query=stripped, limit=limit)


@router.get("/{bucket}", response_model=SearchBucketResponse)
async def search_bucket(
    bucket: str = Path(..., pattern="^(artists|albums)$"),
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    search_service: SearchService = Depends(get_search_service)
):
    results, top_result = await search_service.search_bucket(
        bucket=bucket,
        query=q,
        limit=limit,
        offset=offset
    )
    return SearchBucketResponse(bucket=bucket, limit=limit, offset=offset, results=results, top_result=top_result)


@router.get("/enrich/batch", response_model=EnrichmentResponse)
async def enrich_search_results(
    artist_mbids: str = Query("", description="Comma-separated artist MBIDs"),
    album_mbids: str = Query("", description="Comma-separated album MBIDs"),
    enrichment_service: SearchEnrichmentService = Depends(get_search_enrichment_service)
):
    artist_list = [m.strip() for m in artist_mbids.split(",") if m.strip()]
    album_list = [m.strip() for m in album_mbids.split(",") if m.strip()]

    return await enrichment_service.enrich(
        artist_mbids=artist_list,
        album_mbids=album_list,
    )


@router.post("/enrich/batch", response_model=EnrichmentResponse)
async def enrich_search_results_post(
    body: EnrichmentBatchRequest = MsgSpecBody(EnrichmentBatchRequest),
    enrichment_service: SearchEnrichmentService = Depends(get_search_enrichment_service),
):
    return await enrichment_service.enrich_batch(body)


import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from api.v1.schemas.discover import (
    DiscoverResponse,
    DiscoverQueueResponse,
    DiscoverQueueEnrichment,
    DiscoverQueueIgnoreRequest,
    DiscoverQueueValidateRequest,
    DiscoverQueueValidateResponse,
    YouTubeSearchResponse,
    YouTubeQuotaResponse,
)
from core.dependencies import get_discover_service, get_youtube_repo
from repositories.youtube import YouTubeRepository
from services.discover_service import DiscoverService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.get("", response_model=DiscoverResponse)
async def get_discover_data(
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        return await discover_service.get_discover_data()
    except Exception as e:
        logger.error(f"Failed to get discover data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discover page")


@router.post("/refresh")
async def refresh_discover_data(
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        await discover_service.refresh_discover_data()
        return {"status": "ok", "message": "Discover refresh triggered"}
    except Exception as e:
        logger.error(f"Failed to trigger discover refresh: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger refresh")


@router.get("/queue", response_model=DiscoverQueueResponse)
async def get_discover_queue(
    count: int = 10,
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        return await discover_service.build_queue(count=min(count, 20))
    except Exception as e:
        logger.error(f"Failed to build discover queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to build discover queue")


@router.get("/queue/enrich/{release_group_mbid}", response_model=DiscoverQueueEnrichment)
async def enrich_queue_item(
    release_group_mbid: str,
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        return await discover_service.enrich_queue_item(release_group_mbid)
    except Exception as e:
        logger.error(f"Failed to enrich queue item {release_group_mbid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enrich queue item")


@router.post("/queue/ignore", status_code=204)
async def ignore_queue_item(
    body: DiscoverQueueIgnoreRequest,
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        await discover_service.ignore_release(
            body.release_group_mbid, body.artist_mbid, body.release_name, body.artist_name
        )
    except Exception as e:
        logger.error(f"Failed to ignore queue item: {e}")
        raise HTTPException(status_code=500, detail="Failed to ignore album")


@router.get("/queue/ignored")
async def get_ignored_items(
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        return await discover_service.get_ignored_releases()
    except Exception as e:
        logger.error(f"Failed to get ignored items: {e}")
        raise HTTPException(status_code=500, detail="Failed to get ignored items")


@router.post("/queue/validate", response_model=DiscoverQueueValidateResponse)
async def validate_queue(
    body: DiscoverQueueValidateRequest,
    discover_service: DiscoverService = Depends(get_discover_service),
):
    try:
        in_library = await discover_service.validate_queue_mbids(body.release_group_mbids)
        return DiscoverQueueValidateResponse(in_library=in_library)
    except Exception as e:
        logger.error(f"Failed to validate queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate queue")


@router.get("/queue/youtube-search", response_model=YouTubeSearchResponse)
async def youtube_search(
    artist: str = Query(..., description="Artist name"),
    album: str = Query(..., description="Album name"),
    yt_repo: YouTubeRepository = Depends(get_youtube_repo),
):
    if not yt_repo or not yt_repo.is_configured:
        return YouTubeSearchResponse(error="not_configured")

    if yt_repo.quota_remaining <= 0:
        return YouTubeSearchResponse(error="quota_exceeded")

    video_id = await yt_repo.search_video(artist, album)
    if video_id:
        return YouTubeSearchResponse(
            video_id=video_id,
            embed_url=f"https://www.youtube.com/embed/{video_id}",
        )
    return YouTubeSearchResponse(error="not_found")


@router.get("/queue/youtube-quota", response_model=YouTubeQuotaResponse)
async def youtube_quota(
    yt_repo: YouTubeRepository = Depends(get_youtube_repo),
):
    if not yt_repo or not yt_repo.is_configured:
        raise HTTPException(status_code=404, detail="YouTube not configured")
    return YouTubeQuotaResponse(**yt_repo.get_quota_status())

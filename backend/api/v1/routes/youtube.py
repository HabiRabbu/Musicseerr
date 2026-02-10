import logging

from fastapi import APIRouter, Response

from api.v1.schemas.discover import YouTubeQuotaResponse
from api.v1.schemas.youtube import YouTubeLink, YouTubeLinkGenerateRequest, YouTubeLinkResponse
from core.dependencies import YouTubeServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/youtube", tags=["YouTube"])


@router.post("/generate", response_model=YouTubeLinkResponse)
async def generate_link(
    request: YouTubeLinkGenerateRequest,
    youtube_service: YouTubeServiceDep,
) -> YouTubeLinkResponse:
    link = await youtube_service.generate_link(
        artist_name=request.artist_name,
        album_name=request.album_name,
        album_id=request.album_id,
        cover_url=request.cover_url,
    )
    quota = youtube_service.get_quota_status()
    return YouTubeLinkResponse(
        link=link,
        quota=YouTubeQuotaResponse(**quota),
    )


@router.get("/link/{album_id}", response_model=YouTubeLink | None)
async def get_link(
    album_id: str,
    youtube_service: YouTubeServiceDep,
) -> YouTubeLink | Response:
    link = await youtube_service.get_link(album_id)
    if link is None:
        return Response(status_code=204)
    return link


@router.get("/links", response_model=list[YouTubeLink])
async def get_all_links(
    youtube_service: YouTubeServiceDep,
) -> list[YouTubeLink]:
    return await youtube_service.get_all_links()


@router.delete("/link/{album_id}", status_code=204)
async def delete_link(
    album_id: str,
    youtube_service: YouTubeServiceDep,
) -> None:
    await youtube_service.delete_link(album_id)


@router.get("/quota", response_model=YouTubeQuotaResponse)
async def get_quota(
    youtube_service: YouTubeServiceDep,
) -> YouTubeQuotaResponse:
    quota = youtube_service.get_quota_status()
    return YouTubeQuotaResponse(**quota)

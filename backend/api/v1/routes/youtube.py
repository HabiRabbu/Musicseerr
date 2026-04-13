from fastapi import APIRouter, Response

from api.v1.schemas.discover import YouTubeQuotaResponse
from api.v1.schemas.youtube import (
    YouTubeLink,
    YouTubeLinkGenerateRequest,
    YouTubeLinkResponse,
    YouTubeLinkUpdateRequest,
    YouTubeManualLinkRequest,
    YouTubeTrackLink,
    YouTubeTrackLinkBatchGenerateRequest,
    YouTubeTrackLinkBatchResponse,
    YouTubeTrackLinkGenerateRequest,
    YouTubeTrackLinkResponse,
)
from core.dependencies import YouTubeServiceDep
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute

router = APIRouter(route_class=MsgSpecRoute, prefix="/youtube", tags=["YouTube"])


@router.post("/generate", response_model=YouTubeLinkResponse)
async def generate_link(
    youtube_service: YouTubeServiceDep,
    request: YouTubeLinkGenerateRequest = MsgSpecBody(YouTubeLinkGenerateRequest),
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
        quota=quota,
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


@router.put("/link/{album_id}", response_model=YouTubeLink)
async def update_link(
    album_id: str,
    youtube_service: YouTubeServiceDep,
    request: YouTubeLinkUpdateRequest = MsgSpecBody(YouTubeLinkUpdateRequest),
) -> YouTubeLink:
    return await youtube_service.update_link(
        album_id=album_id,
        youtube_url=request.youtube_url,
        album_name=request.album_name,
        artist_name=request.artist_name,
        cover_url=request.cover_url,
    )


@router.post("/manual", response_model=YouTubeLink)
async def save_manual_link(
    youtube_service: YouTubeServiceDep,
    request: YouTubeManualLinkRequest = MsgSpecBody(YouTubeManualLinkRequest),
) -> YouTubeLink:
    return await youtube_service.save_manual_link(
        album_name=request.album_name,
        artist_name=request.artist_name,
        youtube_url=request.youtube_url,
        cover_url=request.cover_url,
        album_id=request.album_id,
    )


@router.post("/generate-track", response_model=YouTubeTrackLinkResponse)
async def generate_track_link(
    youtube_service: YouTubeServiceDep,
    request: YouTubeTrackLinkGenerateRequest = MsgSpecBody(YouTubeTrackLinkGenerateRequest),
) -> YouTubeTrackLinkResponse:
    track_link = await youtube_service.generate_track_link(
        album_id=request.album_id,
        album_name=request.album_name,
        artist_name=request.artist_name,
        track_name=request.track_name,
        track_number=request.track_number,
        disc_number=request.disc_number,
        cover_url=request.cover_url,
    )
    quota = youtube_service.get_quota_status()
    return YouTubeTrackLinkResponse(
        track_link=track_link,
        quota=quota,
    )


@router.post("/generate-tracks", response_model=YouTubeTrackLinkBatchResponse)
async def generate_track_links_batch(
    youtube_service: YouTubeServiceDep,
    request: YouTubeTrackLinkBatchGenerateRequest = MsgSpecBody(YouTubeTrackLinkBatchGenerateRequest),
) -> YouTubeTrackLinkBatchResponse:
    tracks = [
        {"track_name": t.track_name, "track_number": t.track_number, "disc_number": t.disc_number}
        for t in request.tracks
    ]
    generated, failed = await youtube_service.generate_track_links_batch(
        album_id=request.album_id,
        album_name=request.album_name,
        artist_name=request.artist_name,
        tracks=tracks,
        cover_url=request.cover_url,
    )
    quota = youtube_service.get_quota_status()
    return YouTubeTrackLinkBatchResponse(
        track_links=generated,
        failed=failed,
        quota=quota,
    )


@router.get("/track-links/{album_id}", response_model=list[YouTubeTrackLink])
async def get_track_links(
    album_id: str,
    youtube_service: YouTubeServiceDep,
) -> list[YouTubeTrackLink]:
    return await youtube_service.get_track_links(album_id)


@router.delete("/track-link/{album_id}/{track_number}", status_code=204, deprecated=True)
async def delete_track_link_legacy(
    album_id: str,
    track_number: int,
    youtube_service: YouTubeServiceDep,
) -> None:
    await youtube_service.delete_track_link(album_id, 1, track_number)


@router.delete("/track-link/{album_id}/{disc_number}/{track_number}", status_code=204)
async def delete_track_link(
    album_id: str,
    disc_number: int,
    track_number: int,
    youtube_service: YouTubeServiceDep,
) -> None:
    await youtube_service.delete_track_link(album_id, disc_number, track_number)


@router.get("/quota", response_model=YouTubeQuotaResponse)
async def get_quota(
    youtube_service: YouTubeServiceDep,
) -> YouTubeQuotaResponse:
    return youtube_service.get_quota_status()

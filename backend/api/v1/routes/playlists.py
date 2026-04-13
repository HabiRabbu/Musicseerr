from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from api.v1.schemas.common import StatusMessageResponse
from api.v1.schemas.playlists import (
    AddTracksRequest,
    AddTracksResponse,
    CheckTrackMembershipRequest,
    CheckTrackMembershipResponse,
    CoverUploadResponse,
    CreatePlaylistRequest,
    PlaylistDetailResponse,
    PlaylistListResponse,
    PlaylistSummaryResponse,
    PlaylistTrackResponse,
    RemoveTracksRequest,
    ReorderTrackRequest,
    ReorderTrackResponse,
    ResolveSourcesResponse,
    UpdatePlaylistRequest,
    UpdateTrackRequest,
)
from core.dependencies import JellyfinLibraryServiceDep, LocalFilesServiceDep, NavidromeLibraryServiceDep, PlexLibraryServiceDep, PlaylistServiceDep
from core.exceptions import PlaylistNotFoundError
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute

router = APIRouter(
    route_class=MsgSpecRoute,
    prefix="/playlists",
    tags=["playlists"],
)


def _normalize_cover_url(url: str | None) -> str | None:
    if url and url.startswith("/api/covers/"):
        return "/api/v1/covers/" + url[len("/api/covers/"):]
    return url


def _normalize_source_type(source_type: str) -> str:
    return source_type


def _normalize_available_sources(sources: list[str] | None) -> list[str] | None:
    if sources is None:
        return None
    return sources


def _custom_cover_url(playlist_id: str, cover_image_path: str | None) -> str | None:
    if cover_image_path:
        return f"/api/v1/playlists/{playlist_id}/cover"
    return None


def _track_to_response(t) -> PlaylistTrackResponse:
    return PlaylistTrackResponse(
        id=t.id,
        position=t.position,
        track_name=t.track_name,
        artist_name=t.artist_name,
        album_name=t.album_name,
        album_id=t.album_id,
        artist_id=t.artist_id,
        track_source_id=t.track_source_id,
        cover_url=_normalize_cover_url(t.cover_url),
        source_type=_normalize_source_type(t.source_type),
        available_sources=_normalize_available_sources(t.available_sources),
        format=t.format,
        track_number=t.track_number,
        disc_number=t.disc_number,
        duration=t.duration,
        created_at=t.created_at,
        plex_rating_key=getattr(t, "plex_rating_key", None),
    )


@router.get("", response_model=PlaylistListResponse)
async def list_playlists(
    service: PlaylistServiceDep,
) -> PlaylistListResponse:
    summaries = await service.get_all_playlists()
    return PlaylistListResponse(
        playlists=[
            PlaylistSummaryResponse(
                id=s.id,
                name=s.name,
                track_count=s.track_count,
                total_duration=s.total_duration,
                cover_urls=[_normalize_cover_url(u) for u in s.cover_urls] if s.cover_urls else [],
                custom_cover_url=_custom_cover_url(s.id, s.cover_image_path),
                source_ref=s.source_ref,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in summaries
        ]
    )


@router.post("/check-tracks", response_model=CheckTrackMembershipResponse)
async def check_track_membership(
    service: PlaylistServiceDep,
    body: CheckTrackMembershipRequest = MsgSpecBody(CheckTrackMembershipRequest),
) -> CheckTrackMembershipResponse:
    tracks = [(t.track_name, t.artist_name, t.album_name) for t in body.tracks]
    membership = await service.check_track_membership(tracks)
    return CheckTrackMembershipResponse(membership=membership)


@router.post("", response_model=PlaylistDetailResponse, status_code=201)
async def create_playlist(
    service: PlaylistServiceDep,
    body: CreatePlaylistRequest = MsgSpecBody(CreatePlaylistRequest),
) -> PlaylistDetailResponse:
    playlist = await service.create_playlist(body.name)
    return PlaylistDetailResponse(
        id=playlist.id,
        name=playlist.name,
        custom_cover_url=_custom_cover_url(playlist.id, playlist.cover_image_path),
        source_ref=playlist.source_ref,
        tracks=[],
        track_count=0,
        total_duration=None,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )


@router.get("/{playlist_id}", response_model=PlaylistDetailResponse)
async def get_playlist(
    playlist_id: str,
    service: PlaylistServiceDep,
) -> PlaylistDetailResponse:
    playlist, tracks = await service.get_playlist_with_tracks(playlist_id)
    track_responses = [_track_to_response(t) for t in tracks]
    cover_urls = list(dict.fromkeys(_normalize_cover_url(t.cover_url) for t in tracks if t.cover_url))[:4]
    total_duration = sum(t.duration for t in tracks if t.duration)
    return PlaylistDetailResponse(
        id=playlist.id,
        name=playlist.name,
        cover_urls=cover_urls,
        custom_cover_url=_custom_cover_url(playlist.id, playlist.cover_image_path),
        source_ref=playlist.source_ref,
        tracks=track_responses,
        track_count=len(tracks),
        total_duration=total_duration or None,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )


@router.put("/{playlist_id}", response_model=PlaylistDetailResponse)
async def update_playlist(
    playlist_id: str,
    service: PlaylistServiceDep,
    body: UpdatePlaylistRequest = MsgSpecBody(UpdatePlaylistRequest),
) -> PlaylistDetailResponse:
    playlist, tracks = await service.update_playlist_with_detail(playlist_id, name=body.name)
    track_responses = [_track_to_response(t) for t in tracks]
    cover_urls = list(dict.fromkeys(_normalize_cover_url(t.cover_url) for t in tracks if t.cover_url))[:4]
    total_duration = sum(t.duration for t in tracks if t.duration)
    return PlaylistDetailResponse(
        id=playlist.id,
        name=playlist.name,
        cover_urls=cover_urls,
        custom_cover_url=_custom_cover_url(playlist.id, playlist.cover_image_path),
        source_ref=playlist.source_ref,
        tracks=track_responses,
        track_count=len(tracks),
        total_duration=total_duration or None,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )


@router.delete("/{playlist_id}", response_model=StatusMessageResponse)
async def delete_playlist(
    playlist_id: str,
    service: PlaylistServiceDep,
) -> StatusMessageResponse:
    await service.delete_playlist(playlist_id)
    return StatusMessageResponse(status="ok", message="Playlist deleted")


@router.post(
    "/{playlist_id}/tracks",
    response_model=AddTracksResponse,
    status_code=201,
)
async def add_tracks(
    playlist_id: str,
    service: PlaylistServiceDep,
    body: AddTracksRequest = MsgSpecBody(AddTracksRequest),
) -> AddTracksResponse:
    track_dicts = [
        {
            "track_name": t.track_name,
            "artist_name": t.artist_name,
            "album_name": t.album_name,
            "album_id": t.album_id,
            "artist_id": t.artist_id,
            "track_source_id": t.track_source_id,
            "cover_url": t.cover_url,
            "source_type": t.source_type,
            "available_sources": t.available_sources,
            "format": t.format,
            "track_number": t.track_number,
            "disc_number": t.disc_number,
            "duration": int(t.duration) if t.duration is not None else None,
            "plex_rating_key": t.plex_rating_key,
        }
        for t in body.tracks
    ]
    created = await service.add_tracks(playlist_id, track_dicts, body.position)
    return AddTracksResponse(tracks=[_track_to_response(t) for t in created])


@router.post(
    "/{playlist_id}/tracks/remove",
    response_model=StatusMessageResponse,
)
async def remove_tracks(
    playlist_id: str,
    service: PlaylistServiceDep,
    body: RemoveTracksRequest = MsgSpecBody(RemoveTracksRequest),
) -> StatusMessageResponse:
    removed = await service.remove_tracks(playlist_id, body.track_ids)
    return StatusMessageResponse(status="ok", message=f"{removed} track(s) removed")


@router.delete(
    "/{playlist_id}/tracks/{track_id}",
    response_model=StatusMessageResponse,
)
async def remove_track(
    playlist_id: str,
    track_id: str,
    service: PlaylistServiceDep,
) -> StatusMessageResponse:
    await service.remove_track(playlist_id, track_id)
    return StatusMessageResponse(status="ok", message="Track removed")


# Reorder must be registered before the {track_id} PATCH to avoid
# "reorder" being captured as a track_id path parameter.
@router.patch(
    "/{playlist_id}/tracks/reorder",
    response_model=ReorderTrackResponse,
)
async def reorder_track(
    playlist_id: str,
    service: PlaylistServiceDep,
    body: ReorderTrackRequest = MsgSpecBody(ReorderTrackRequest),
) -> ReorderTrackResponse:
    actual_position = await service.reorder_track(playlist_id, body.track_id, body.new_position)
    return ReorderTrackResponse(
        status="ok",
        message="Track reordered",
        actual_position=actual_position,
    )


@router.patch(
    "/{playlist_id}/tracks/{track_id}",
    response_model=PlaylistTrackResponse,
)
async def update_track(
    playlist_id: str,
    track_id: str,
    service: PlaylistServiceDep,
    jf_service: JellyfinLibraryServiceDep,
    local_service: LocalFilesServiceDep,
    nd_service: NavidromeLibraryServiceDep,
    plex_service: PlexLibraryServiceDep,
    body: UpdateTrackRequest = MsgSpecBody(UpdateTrackRequest),
) -> PlaylistTrackResponse:
    result = await service.update_track_source(
        playlist_id, track_id,
        source_type=body.source_type,
        available_sources=body.available_sources,
        jf_service=jf_service,
        local_service=local_service,
        nd_service=nd_service,
        plex_service=plex_service,
    )
    return _track_to_response(result)


@router.post(
    "/{playlist_id}/resolve-sources",
    response_model=ResolveSourcesResponse,
)
async def resolve_sources(
    playlist_id: str,
    service: PlaylistServiceDep,
    jf_service: JellyfinLibraryServiceDep,
    local_service: LocalFilesServiceDep,
    nd_service: NavidromeLibraryServiceDep,
    plex_service: PlexLibraryServiceDep,
) -> ResolveSourcesResponse:
    sources = await service.resolve_track_sources(
        playlist_id, jf_service=jf_service, local_service=local_service,
        nd_service=nd_service, plex_service=plex_service,
    )
    return ResolveSourcesResponse(sources=sources)


@router.post("/{playlist_id}/cover", response_model=CoverUploadResponse)
async def upload_cover(
    playlist_id: str,
    service: PlaylistServiceDep,
    cover_image: UploadFile = File(...),
) -> CoverUploadResponse:
    max_size = 2 * 1024 * 1024
    chunk_size = 8192
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await cover_image.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            from core.exceptions import InvalidPlaylistDataError
            raise InvalidPlaylistDataError("Image too large. Maximum size is 2 MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    cover_url = await service.upload_cover(
        playlist_id, data, cover_image.content_type or "",
    )
    return CoverUploadResponse(cover_url=cover_url)


@router.get("/{playlist_id}/cover")
async def get_cover(
    playlist_id: str,
    service: PlaylistServiceDep,
):
    path = await service.get_cover_path(playlist_id)
    if path is None:
        raise PlaylistNotFoundError("No cover found")

    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")

    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.delete(
    "/{playlist_id}/cover",
    response_model=StatusMessageResponse,
)
async def remove_cover(
    playlist_id: str,
    service: PlaylistServiceDep,
) -> StatusMessageResponse:
    await service.remove_cover(playlist_id)
    return StatusMessageResponse(status="ok", message="Cover removed")

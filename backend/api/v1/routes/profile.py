import asyncio
import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from api.v1.schemas.profile import (
    ProfileResponse,
    ProfileSettings,
    ProfileUpdateRequest,
    ServiceConnection,
    LibraryStats,
)
from core.dependencies import (
    get_preferences_service,
    get_jellyfin_library_service,
    get_local_files_service,
    get_navidrome_library_service,
    get_settings_service,
)
from core.config import Settings, get_settings
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.preferences_service import PreferencesService
from services.jellyfin_library_service import JellyfinLibraryService
from services.local_files_service import LocalFilesService
from services.navidrome_library_service import NavidromeLibraryService

logger = logging.getLogger(__name__)

AVATAR_DIR_NAME = "profile"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB

router = APIRouter(route_class=MsgSpecRoute, prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
async def get_profile(
    preferences: PreferencesService = Depends(get_preferences_service),
    jellyfin_service: JellyfinLibraryService = Depends(get_jellyfin_library_service),
    local_service: LocalFilesService = Depends(get_local_files_service),
    navidrome_service: NavidromeLibraryService = Depends(get_navidrome_library_service),
) -> ProfileResponse:
    profile = preferences.get_profile_settings()

    services: list[ServiceConnection] = []
    library_stats_list: list[LibraryStats] = []

    jellyfin_conn = preferences.get_jellyfin_connection()
    services.append(ServiceConnection(
        name="Jellyfin",
        enabled=jellyfin_conn.enabled,
        username=jellyfin_conn.user_id,
        url=jellyfin_conn.jellyfin_url,
    ))

    lb_conn = preferences.get_listenbrainz_connection()
    services.append(ServiceConnection(
        name="ListenBrainz",
        enabled=lb_conn.enabled,
        username=lb_conn.username,
        url="https://listenbrainz.org",
    ))

    lastfm_conn = preferences.get_lastfm_connection()
    services.append(ServiceConnection(
        name="Last.fm",
        enabled=lastfm_conn.enabled,
        username=lastfm_conn.username,
        url="https://www.last.fm",
    ))

    navidrome_conn = preferences.get_navidrome_connection()
    services.append(ServiceConnection(
        name="Navidrome",
        enabled=navidrome_conn.enabled,
        username=navidrome_conn.username,
        url=navidrome_conn.navidrome_url,
    ))

    local_conn = preferences.get_local_files_connection()

    async def _fetch_jellyfin_stats() -> LibraryStats | None:
        if not jellyfin_conn.enabled:
            return None
        try:
            s = await jellyfin_service.get_stats()
            return LibraryStats(source="Jellyfin", total_tracks=s.total_tracks, total_albums=s.total_albums, total_artists=s.total_artists)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to fetch Jellyfin stats for profile: %s", e)
            return None

    async def _fetch_local_stats() -> LibraryStats | None:
        if not local_conn.enabled:
            return None
        try:
            s = await local_service.get_storage_stats()
            return LibraryStats(source="Local Files", total_tracks=s.total_tracks, total_albums=s.total_albums, total_artists=s.total_artists, total_size_bytes=s.total_size_bytes, total_size_human=s.total_size_human)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to fetch Local Files stats for profile: %s", e)
            return None

    async def _fetch_navidrome_stats() -> LibraryStats | None:
        if not navidrome_conn.enabled:
            return None
        try:
            s = await navidrome_service.get_stats()
            return LibraryStats(source="Navidrome", total_tracks=s.total_tracks, total_albums=s.total_albums, total_artists=s.total_artists)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to fetch Navidrome stats for profile: %s", e)
            return None

    results = await asyncio.gather(_fetch_jellyfin_stats(), _fetch_local_stats(), _fetch_navidrome_stats())
    library_stats_list = [r for r in results if r is not None]

    return ProfileResponse(
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        services=services,
        library_stats=library_stats_list,
    )


@router.put("", response_model=ProfileSettings)
async def update_profile(
    body: ProfileUpdateRequest = MsgSpecBody(ProfileUpdateRequest),
    preferences: PreferencesService = Depends(get_preferences_service),
) -> ProfileSettings:
    current = preferences.get_profile_settings()

    updated = ProfileSettings(
        display_name=body.display_name if body.display_name is not None else current.display_name,
        avatar_url=body.avatar_url if body.avatar_url is not None else current.avatar_url,
    )

    preferences.save_profile_settings(updated)
    return updated


def _get_avatar_dir() -> Path:
    settings = get_settings()
    avatar_dir = settings.cache_dir / AVATAR_DIR_NAME
    avatar_dir.mkdir(parents=True, exist_ok=True)
    return avatar_dir


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    preferences: PreferencesService = Depends(get_preferences_service),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type. Allowed: JPEG, PNG, WebP, GIF")

    data = await file.read()
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 5 MB")

    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(file.content_type, ".jpg")

    avatar_dir = _get_avatar_dir()

    # Remove old avatar files
    for old_file in avatar_dir.glob("avatar.*"):
        try:
            old_file.unlink()
        except OSError:
            pass

    filename = f"avatar{ext}"
    file_path = avatar_dir / filename
    file_path.write_bytes(data)

    avatar_url = "/api/v1/profile/avatar"
    current = preferences.get_profile_settings()
    updated = ProfileSettings(
        display_name=current.display_name,
        avatar_url=avatar_url,
    )
    preferences.save_profile_settings(updated)

    return {"avatar_url": avatar_url}


@router.get("/avatar")
async def get_avatar():
    avatar_dir = _get_avatar_dir()
    for ext in (".jpg", ".png", ".webp", ".gif"):
        file_path = avatar_dir / f"avatar{ext}"
        if file_path.exists():
            media_type = {
                ".jpg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }[ext]
            return FileResponse(
                file_path,
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )
    raise HTTPException(status_code=404, detail="No avatar found")

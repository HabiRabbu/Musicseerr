from typing import Literal

import msgspec

from api.v1.schemas.plex import PlexLibrarySectionInfo
from infrastructure.msgspec_fastapi import AppStruct

LASTFM_SECRET_MASK = "••••••••"


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return LASTFM_SECRET_MASK
    return LASTFM_SECRET_MASK + value[-4:]


def _is_masked(value: str) -> bool:
    """Return True if value is a masked placeholder produced by _mask_secret()."""
    return bool(value) and value.startswith(LASTFM_SECRET_MASK)


class LastFmConnectionSettings(AppStruct):
    api_key: str = ""
    shared_secret: str = ""
    session_key: str = ""
    username: str = ""
    enabled: bool = False


class LastFmConnectionSettingsResponse(AppStruct):
    api_key: str = ""
    shared_secret: str = ""
    session_key: str = ""
    username: str = ""
    enabled: bool = False

    @classmethod
    def from_settings(cls, settings: LastFmConnectionSettings) -> "LastFmConnectionSettingsResponse":
        return cls(
            api_key=_mask_secret(settings.api_key),
            shared_secret=_mask_secret(settings.shared_secret),
            session_key=_mask_secret(settings.session_key),
            username=settings.username,
            enabled=settings.enabled,
        )


class LastFmVerifyResponse(AppStruct):
    valid: bool
    message: str


class LastFmAuthTokenResponse(AppStruct):
    token: str
    auth_url: str


class LastFmAuthSessionRequest(AppStruct):
    token: str


class LastFmAuthSessionResponse(AppStruct):
    success: bool
    message: str
    username: str = ""


class UserPreferences(AppStruct):
    primary_types: list[str] = msgspec.field(default_factory=lambda: ["album", "ep", "single"])
    secondary_types: list[str] = msgspec.field(default_factory=lambda: ["studio"])
    release_statuses: list[str] = msgspec.field(default_factory=lambda: ["official"])


class LidarrConnectionSettings(AppStruct):
    lidarr_url: str = "http://lidarr:8686"
    lidarr_api_key: str = ""
    quality_profile_id: int = 1
    metadata_profile_id: int = 1
    root_folder_path: str = "/music"

    def __post_init__(self) -> None:
        self.lidarr_url = self.lidarr_url.rstrip("/")
        if self.quality_profile_id < 1:
            raise msgspec.ValidationError("quality_profile_id must be >= 1")
        if self.metadata_profile_id < 1:
            raise msgspec.ValidationError("metadata_profile_id must be >= 1")


class JellyfinConnectionSettings(AppStruct):
    jellyfin_url: str = "http://jellyfin:8096"
    api_key: str = ""
    user_id: str = ""
    enabled: bool = False

    def __post_init__(self) -> None:
        self.jellyfin_url = self.jellyfin_url.rstrip("/")


NAVIDROME_PASSWORD_MASK = "********"
PLEX_TOKEN_MASK = "plex****"


class NavidromeConnectionSettings(AppStruct):
    navidrome_url: str = ""
    username: str = ""
    password: str = ""
    enabled: bool = False

    def __post_init__(self) -> None:
        self.navidrome_url = self.navidrome_url.rstrip("/") if self.navidrome_url else ""


class PlexConnectionSettings(AppStruct):
    plex_url: str = ""
    plex_token: str = ""
    enabled: bool = False
    music_library_ids: list[str] = []
    scrobble_to_plex: bool = True

    def __post_init__(self) -> None:
        self.plex_url = self.plex_url.rstrip("/") if self.plex_url else ""


class NavidromeConnectionSettingsResponse(AppStruct):
    navidrome_url: str = ""
    username: str = ""
    password: str = ""
    enabled: bool = False

    @classmethod
    def from_settings(cls, s: "NavidromeConnectionSettings") -> "NavidromeConnectionSettingsResponse":
        return cls(
            navidrome_url=s.navidrome_url,
            username=s.username,
            password=_mask_secret(s.password),
            enabled=s.enabled,
        )


class PlexConnectionSettingsResponse(AppStruct):
    plex_url: str = ""
    plex_token: str = ""
    enabled: bool = False
    music_library_ids: list[str] = []
    scrobble_to_plex: bool = True

    @classmethod
    def from_settings(cls, s: "PlexConnectionSettings") -> "PlexConnectionSettingsResponse":
        return cls(
            plex_url=s.plex_url,
            plex_token=_mask_secret(s.plex_token),
            enabled=s.enabled,
            music_library_ids=s.music_library_ids,
            scrobble_to_plex=s.scrobble_to_plex,
        )


class JellyfinConnectionSettingsResponse(AppStruct):
    jellyfin_url: str = ""
    api_key: str = ""
    user_id: str = ""
    enabled: bool = False

    @classmethod
    def from_settings(cls, s: "JellyfinConnectionSettings") -> "JellyfinConnectionSettingsResponse":
        return cls(
            jellyfin_url=s.jellyfin_url,
            api_key=_mask_secret(s.api_key),
            user_id=s.user_id,
            enabled=s.enabled,
        )


class LidarrConnectionSettingsResponse(AppStruct):
    lidarr_url: str = "http://lidarr:8686"
    lidarr_api_key: str = ""
    quality_profile_id: int = 1
    metadata_profile_id: int = 1
    root_folder_path: str = "/music"

    @classmethod
    def from_settings(cls, s: "LidarrConnectionSettings") -> "LidarrConnectionSettingsResponse":
        return cls(
            lidarr_url=s.lidarr_url,
            lidarr_api_key=_mask_secret(s.lidarr_api_key),
            quality_profile_id=s.quality_profile_id,
            metadata_profile_id=s.metadata_profile_id,
            root_folder_path=s.root_folder_path,
        )


class YouTubeConnectionSettingsResponse(AppStruct):
    api_key: str = ""
    enabled: bool = False
    api_enabled: bool = False
    daily_quota_limit: int = 80

    @classmethod
    def from_settings(cls, s: "YouTubeConnectionSettings") -> "YouTubeConnectionSettingsResponse":
        return cls(
            api_key=_mask_secret(s.api_key),
            enabled=s.enabled,
            api_enabled=s.api_enabled,
            daily_quota_limit=s.daily_quota_limit,
        )


class ListenBrainzConnectionSettingsResponse(AppStruct):
    username: str = ""
    user_token: str = ""
    enabled: bool = False

    @classmethod
    def from_settings(cls, s: "ListenBrainzConnectionSettings") -> "ListenBrainzConnectionSettingsResponse":
        return cls(
            username=s.username,
            user_token=_mask_secret(s.user_token),
            enabled=s.enabled,
        )


class PlexVerifyResponse(AppStruct):
    valid: bool
    message: str
    libraries: list[PlexLibrarySectionInfo] = []


class PlexOAuthPinResponse(AppStruct):
    pin_id: int
    pin_code: str
    auth_url: str


class PlexOAuthPollResponse(AppStruct):
    completed: bool
    auth_token: str = ""


class JellyfinUserInfo(AppStruct):
    id: str
    name: str


class JellyfinVerifyResponse(AppStruct):
    success: bool
    message: str
    users: list[JellyfinUserInfo] = []


class ListenBrainzConnectionSettings(AppStruct):
    username: str = ""
    user_token: str = ""
    enabled: bool = False


class YouTubeConnectionSettings(AppStruct):
    api_key: str = ""
    enabled: bool = False
    api_enabled: bool = False
    daily_quota_limit: int = 80

    def __post_init__(self) -> None:
        if self.daily_quota_limit < 1 or self.daily_quota_limit > 10000:
            raise msgspec.ValidationError("daily_quota_limit must be between 1 and 10000")

    def has_valid_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


class HomeSettings(AppStruct):
    cache_ttl_trending: int = 3600
    cache_ttl_personal: int = 300

    def __post_init__(self) -> None:
        if self.cache_ttl_trending < 300 or self.cache_ttl_trending > 86400:
            raise msgspec.ValidationError("cache_ttl_trending must be between 300 and 86400")
        if self.cache_ttl_personal < 60 or self.cache_ttl_personal > 3600:
            raise msgspec.ValidationError("cache_ttl_personal must be between 60 and 3600")


class LocalFilesConnectionSettings(AppStruct):
    enabled: bool = False
    music_path: str = "/music"
    lidarr_root_path: str = "/music"


class LocalFilesVerifyResponse(AppStruct):
    success: bool
    message: str
    track_count: int = 0


class LidarrSettings(AppStruct):
    sync_frequency: Literal["manual", "5min", "10min", "30min", "1hr", "6hr", "12hr", "24hr", "3d", "7d"] = "24hr"
    last_sync: int | None = None
    last_sync_success: bool = True


class LidarrProfileSummary(AppStruct):
    id: int
    name: str


class LidarrRootFolderSummary(AppStruct):
    id: str
    path: str


class LidarrVerifyResponse(AppStruct):
    success: bool
    message: str
    quality_profiles: list[LidarrProfileSummary] = []
    metadata_profiles: list[LidarrProfileSummary] = []
    root_folders: list[LidarrRootFolderSummary] = []


class LidarrMetadataProfileSummary(AppStruct):
    id: int
    name: str


class ScrobbleSettings(AppStruct):
    scrobble_to_lastfm: bool = False
    scrobble_to_listenbrainz: bool = False


class PrimaryMusicSourceSettings(AppStruct):
    source: Literal["listenbrainz", "lastfm"] = "listenbrainz"


class LidarrMetadataProfilePreferences(AppStruct):
    profile_id: int
    profile_name: str
    primary_types: list[str] = []
    secondary_types: list[str] = []
    release_statuses: list[str] = []


class EmbyAuthSettings(AppStruct):
    emby_url: str = ""
    enabled: bool = False


class EmbyVerifyResponse(AppStruct):
    success: bool
    message: str


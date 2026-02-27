from pydantic import BaseModel, Field, field_validator
from typing import Literal

LASTFM_SECRET_MASK = "••••••••"


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return LASTFM_SECRET_MASK
    return LASTFM_SECRET_MASK + value[-4:]


class LastFmConnectionSettings(BaseModel):
    api_key: str = Field(default="", description="Last.fm API key")
    shared_secret: str = Field(default="", description="Last.fm shared secret")
    session_key: str = Field(default="", description="Last.fm session key (obtained via auth flow)")
    username: str = Field(default="", description="Last.fm username (set after authorization)")
    enabled: bool = Field(default=False, description="Whether Last.fm integration is enabled")


class LastFmConnectionSettingsResponse(BaseModel):
    api_key: str = Field(default="", description="Last.fm API key (returned in full)")
    shared_secret: str = Field(default="", description="Last.fm shared secret (masked)")
    session_key: str = Field(default="", description="Last.fm session key (masked)")
    username: str = Field(default="", description="Last.fm username")
    enabled: bool = Field(default=False, description="Whether Last.fm integration is enabled")

    @classmethod
    def from_settings(cls, settings: LastFmConnectionSettings) -> "LastFmConnectionSettingsResponse":
        return cls(
            api_key=settings.api_key,
            shared_secret=_mask_secret(settings.shared_secret),
            session_key=_mask_secret(settings.session_key),
            username=settings.username,
            enabled=settings.enabled,
        )


class LastFmVerifyResponse(BaseModel):
    valid: bool = Field(description="Whether the connection is valid")
    message: str = Field(description="Status message")


class LastFmAuthTokenResponse(BaseModel):
    token: str = Field(description="Last.fm request token")
    auth_url: str = Field(description="URL to authorize the token on Last.fm")


class LastFmAuthSessionRequest(BaseModel):
    token: str = Field(description="Last.fm request token to exchange for a session")


class LastFmAuthSessionResponse(BaseModel):
    username: str = Field(default="", description="Last.fm username")
    success: bool = Field(description="Whether session exchange succeeded")
    message: str = Field(description="Status message")


class UserPreferences(BaseModel):
    primary_types: list[str] = Field(
        default=["album", "ep", "single"],
        description="Included primary release types"
    )
    secondary_types: list[str] = Field(
        default=["studio"],
        description="Included secondary release types"
    )
    release_statuses: list[str] = Field(
        default=["official"],
        description="Included release statuses"
    )


class LidarrConnectionSettings(BaseModel):
    lidarr_url: str = Field(
        default="http://lidarr:8686",
        description="Lidarr server URL"
    )
    lidarr_api_key: str = Field(
        default="",
        description="Lidarr API key"
    )
    quality_profile_id: int = Field(
        default=1,
        ge=1,
        description="Default quality profile ID for new artists"
    )
    metadata_profile_id: int = Field(
        default=1,
        ge=1,
        description="Default metadata profile ID for new artists"
    )
    root_folder_path: str = Field(
        default="/music",
        description="Root folder path for music library"
    )
    
    @field_validator("lidarr_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return v.rstrip("/")


class JellyfinConnectionSettings(BaseModel):
    jellyfin_url: str = Field(
        default="http://jellyfin:8096",
        description="Jellyfin server URL"
    )
    api_key: str = Field(
        default="",
        description="Jellyfin API key for authentication"
    )
    user_id: str = Field(
        default="",
        description="Jellyfin user ID for user-specific data"
    )
    enabled: bool = Field(
        default=False,
        description="Whether Jellyfin integration is enabled"
    )
    
    @field_validator("jellyfin_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return v.rstrip("/")


class ListenBrainzConnectionSettings(BaseModel):
    username: str = Field(
        default="",
        description="ListenBrainz username"
    )
    user_token: str = Field(
        default="",
        description="ListenBrainz user token for authenticated requests"
    )
    enabled: bool = Field(
        default=False,
        description="Whether ListenBrainz integration is enabled"
    )


class YouTubeConnectionSettings(BaseModel):
    api_key: str = Field(
        default="",
        description="YouTube Data API v3 key"
    )
    enabled: bool = Field(
        default=False,
        description="Whether YouTube integration is enabled"
    )
    daily_quota_limit: int = Field(
        default=80,
        description="Maximum YouTube API searches per day",
        ge=1,
        le=10000,
    )


class HomeSettings(BaseModel):
    cache_ttl_trending: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Cache TTL for trending/popular data in seconds (default: 1 hour)"
    )
    cache_ttl_personal: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache TTL for personalized data in seconds (default: 5 minutes)"
    )


class LocalFilesConnectionSettings(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Whether local file playback is enabled"
    )
    music_path: str = Field(
        default="/music",
        description="Container-internal path to mounted music directory"
    )
    lidarr_root_path: str = Field(
        default="/music",
        description="Lidarr root folder path (used to map file paths)"
    )


class LocalFilesVerifyResponse(BaseModel):
    success: bool = Field(description="Whether the path is valid and readable")
    message: str = Field(description="Status message")
    track_count: int = Field(default=0, description="Number of audio files found")


class LidarrSettings(BaseModel):
    sync_frequency: Literal["manual", "5min", "10min", "30min", "1hr"] = Field(
        default="10min",
        description="How often to sync library from Lidarr"
    )
    last_sync: int | None = Field(
        default=None,
        description="Unix timestamp of last sync attempt (success or failure)"
    )
    last_sync_success: bool = Field(
        default=True,
        description="Whether the last sync completed successfully"
    )


class LidarrVerifyResponse(BaseModel):
    success: bool = Field(description="Whether connection was successful")
    message: str = Field(description="Status message")
    quality_profiles: list[dict[str, int | str]] = Field(
        default_factory=list,
        description="Available quality profiles"
    )
    metadata_profiles: list[dict[str, int | str]] = Field(
        default_factory=list,
        description="Available metadata profiles"
    )
    root_folders: list[dict[str, str]] = Field(
        default_factory=list,
        description="Available root folders"
    )


class LidarrMetadataProfileSummary(BaseModel):
    id: int = Field(description="Lidarr metadata profile ID")
    name: str = Field(description="Lidarr metadata profile name")


class ScrobbleSettings(BaseModel):
    scrobble_to_lastfm: bool = Field(
        default=False, description="Whether to send scrobbles to Last.fm"
    )
    scrobble_to_listenbrainz: bool = Field(
        default=False, description="Whether to send scrobbles to ListenBrainz"
    )


class PrimaryMusicSourceSettings(BaseModel):
    source: Literal["listenbrainz", "lastfm"] = Field(
        default="listenbrainz",
        description="Primary music data source for home/discover pages",
    )


class LidarrMetadataProfilePreferences(BaseModel):
    profile_id: int = Field(description="Lidarr metadata profile ID")
    profile_name: str = Field(description="Lidarr metadata profile name")
    primary_types: list[str] = Field(
        default_factory=list,
        description="Primary release types enabled in Lidarr profile"
    )
    secondary_types: list[str] = Field(
        default_factory=list,
        description="Secondary release types enabled in Lidarr profile"
    )
    release_statuses: list[str] = Field(
        default_factory=list,
        description="Release statuses enabled in Lidarr profile"
    )

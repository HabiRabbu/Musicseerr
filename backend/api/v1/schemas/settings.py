from pydantic import BaseModel, Field, field_validator
from typing import Literal


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


class SoularrConnectionSettings(BaseModel):
    soularr_url: str = Field(
        default="http://soularr:8181",
        description="Soularr server URL"
    )
    soularr_api_key: str = Field(
        default="",
        description="Soularr API key"
    )
    trigger_soularr: bool = Field(
        default=False,
        description="Automatically trigger Soularr after adding to Lidarr"
    )
    
    @field_validator("soularr_url")
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

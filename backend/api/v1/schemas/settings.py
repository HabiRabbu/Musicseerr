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
    
    @field_validator("jellyfin_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return v.rstrip("/")


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

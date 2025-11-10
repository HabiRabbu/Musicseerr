from pydantic import BaseModel, Field
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

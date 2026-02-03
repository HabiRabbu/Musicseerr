from pydantic import BaseModel, Field
from typing import Optional


class CacheSyncStatus(BaseModel):
    is_syncing: bool = Field(..., description="Whether a cache sync is in progress")
    phase: Optional[str] = Field(None, description="Current sync phase (artists/albums/warming)")
    total_items: int = Field(0, description="Total items to process in current phase")
    processed_items: int = Field(0, description="Items processed so far")
    progress_percent: int = Field(0, description="Progress percentage (0-100)")
    current_item: Optional[str] = Field(None, description="Currently processing item")
    started_at: Optional[float] = Field(None, description="Unix timestamp when sync started")
    error_message: Optional[str] = Field(None, description="Error message if sync failed")
    total_artists: int = Field(0, description="Total artists to process")
    processed_artists: int = Field(0, description="Artists processed so far")
    total_albums: int = Field(0, description="Total albums to process")
    processed_albums: int = Field(0, description="Albums processed so far")

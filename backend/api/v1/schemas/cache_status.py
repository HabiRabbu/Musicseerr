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

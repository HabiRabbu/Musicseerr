"""Cache-related schemas."""
from pydantic import BaseModel, Field


class CacheStats(BaseModel):
    """Cache statistics."""
    memory_entries: int = Field(..., description="Number of entries in memory cache")
    memory_size_bytes: int = Field(..., description="Estimated memory usage in bytes")
    memory_size_mb: float = Field(..., description="Estimated memory usage in MB")
    disk_cover_count: int = Field(..., description="Number of cover images on disk")
    disk_cover_size_bytes: int = Field(..., description="Total size of cover images in bytes")
    disk_cover_size_mb: float = Field(..., description="Total size of cover images in MB")
    total_size_bytes: int = Field(..., description="Total cache size (memory + disk) in bytes")
    total_size_mb: float = Field(..., description="Total cache size (memory + disk) in MB")


class CacheClearResponse(BaseModel):
    """Response for cache clearing operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Result message")
    cleared_memory_entries: int = Field(0, description="Number of memory entries cleared")
    cleared_disk_files: int = Field(0, description="Number of disk files cleared")

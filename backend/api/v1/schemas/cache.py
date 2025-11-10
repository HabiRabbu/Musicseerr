from pydantic import BaseModel, Field


class CacheStats(BaseModel):
    memory_entries: int = Field(..., description="Number of entries in memory cache (hot items only)")
    memory_size_bytes: int = Field(..., description="Estimated memory usage in bytes")
    memory_size_mb: float = Field(..., description="Estimated memory usage in MB")
    disk_metadata_count: int = Field(..., description="Total metadata entries on disk (albums + artists)")
    disk_metadata_albums: int = Field(..., description="Number of album metadata JSON files on disk")
    disk_metadata_artists: int = Field(..., description="Number of artist metadata JSON files on disk")
    disk_cover_count: int = Field(..., description="Number of cover images on disk")
    disk_cover_size_bytes: int = Field(..., description="Total size of cover images in bytes")
    disk_cover_size_mb: float = Field(..., description="Total size of cover images in MB")
    library_db_artist_count: int = Field(..., description="Number of artists in library database")
    library_db_album_count: int = Field(..., description="Number of albums in library database")
    library_db_size_bytes: int = Field(..., description="Size of library database in bytes")
    library_db_size_mb: float = Field(..., description="Size of library database in MB")
    library_db_last_sync: int | None = Field(None, description="Unix timestamp of last library sync")
    total_size_bytes: int = Field(..., description="Total cache size (memory + disk + library) in bytes")
    total_size_mb: float = Field(..., description="Total cache size (memory + disk + library) in MB")


class CacheClearResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Result message")
    cleared_memory_entries: int = Field(0, description="Number of memory entries cleared")
    cleared_disk_files: int = Field(0, description="Number of disk files cleared")
    cleared_library_artists: int = Field(0, description="Number of library artists cleared")
    cleared_library_albums: int = Field(0, description="Number of library albums cleared")

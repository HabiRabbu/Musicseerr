from infrastructure.msgspec_fastapi import AppStruct


class CacheStats(AppStruct):
    memory_entries: int
    memory_size_bytes: int
    memory_size_mb: float
    disk_metadata_count: int
    disk_metadata_albums: int
    disk_metadata_artists: int
    disk_cover_count: int
    disk_cover_size_bytes: int
    disk_cover_size_mb: float
    library_db_artist_count: int
    library_db_album_count: int
    library_db_size_bytes: int
    library_db_size_mb: float
    total_size_bytes: int
    total_size_mb: float
    library_db_last_sync: int | None = None


class CacheClearResponse(AppStruct):
    success: bool
    message: str
    cleared_memory_entries: int = 0
    cleared_disk_files: int = 0
    cleared_library_artists: int = 0
    cleared_library_albums: int = 0

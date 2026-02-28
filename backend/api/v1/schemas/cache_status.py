from infrastructure.msgspec_fastapi import AppStruct


class CacheSyncStatus(AppStruct):
    is_syncing: bool
    phase: str | None = None
    total_items: int = 0
    processed_items: int = 0
    progress_percent: int = 0
    current_item: str | None = None
    started_at: float | None = None
    error_message: str | None = None
    total_artists: int = 0
    processed_artists: int = 0
    total_albums: int = 0
    processed_albums: int = 0

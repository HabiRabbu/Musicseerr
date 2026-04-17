from infrastructure.msgspec_fastapi import AppStruct


class LocalTrackInfo(AppStruct):
    track_file_id: int
    title: str
    track_number: int
    disc_number: int = 1
    duration_seconds: float | None = None
    size_bytes: int = 0
    format: str = ""
    bitrate: int | None = None
    date_added: str | None = None


class LocalAlbumMatch(AppStruct):
    found: bool
    lidarr_album_id: int | None = None
    tracks: list[LocalTrackInfo] = []
    total_size_bytes: int = 0
    primary_format: str | None = None


class LocalAlbumSummary(AppStruct):
    lidarr_album_id: int
    musicbrainz_id: str
    name: str
    artist_name: str
    artist_mbid: str | None = None
    year: int | None = None
    track_count: int = 0
    total_size_bytes: int = 0
    primary_format: str | None = None
    cover_url: str | None = None
    date_added: str | None = None


class LocalPaginatedResponse(AppStruct):
    items: list[LocalAlbumSummary] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


class FormatInfo(AppStruct):
    count: int = 0
    size_bytes: int = 0
    size_human: str = "0 B"


class LocalStorageStats(AppStruct):
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0
    total_size_bytes: int = 0
    total_size_human: str = "0 B"
    disk_free_bytes: int = 0
    disk_free_human: str = "0 B"
    format_breakdown: dict[str, FormatInfo] = {}

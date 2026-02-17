from pydantic import BaseModel, Field


class LocalTrackInfo(BaseModel):
    track_file_id: int
    title: str
    track_number: int
    duration_seconds: float | None = None
    size_bytes: int = 0
    format: str = ""
    bitrate: int | None = None
    date_added: str | None = None


class LocalAlbumMatch(BaseModel):
    found: bool
    tracks: list[LocalTrackInfo] = Field(default_factory=list)
    total_size_bytes: int = 0
    primary_format: str | None = None


class LocalAlbumSummary(BaseModel):
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


class LocalPaginatedResponse(BaseModel):
    items: list[LocalAlbumSummary] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class FormatInfo(BaseModel):
    count: int = 0
    size_bytes: int = 0
    size_human: str = "0 B"


class LocalStorageStats(BaseModel):
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0
    total_size_bytes: int = 0
    total_size_human: str = "0 B"
    disk_free_bytes: int = 0
    disk_free_human: str = "0 B"
    format_breakdown: dict[str, FormatInfo] = Field(default_factory=dict)

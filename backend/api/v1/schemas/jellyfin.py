from pydantic import BaseModel, Field


class JellyfinTrackInfo(BaseModel):
    jellyfin_id: str = Field(description="Jellyfin item ID")
    title: str
    track_number: int
    duration_seconds: float = Field(ge=0)
    album_name: str = ""
    artist_name: str = ""
    codec: str | None = None
    bitrate: int | None = None


class JellyfinAlbumSummary(BaseModel):
    jellyfin_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    musicbrainz_id: str | None = None
    artist_musicbrainz_id: str | None = None


class JellyfinAlbumDetail(BaseModel):
    jellyfin_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    musicbrainz_id: str | None = None
    artist_musicbrainz_id: str | None = None
    tracks: list[JellyfinTrackInfo] = Field(default_factory=list)


class JellyfinAlbumMatch(BaseModel):
    found: bool
    jellyfin_album_id: str | None = None
    tracks: list[JellyfinTrackInfo] = Field(default_factory=list)


class JellyfinArtistSummary(BaseModel):
    jellyfin_id: str
    name: str
    image_url: str | None = None
    album_count: int = 0
    musicbrainz_id: str | None = None


class JellyfinLibraryStats(BaseModel):
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0


class JellyfinSearchResponse(BaseModel):
    albums: list[JellyfinAlbumSummary] = Field(default_factory=list)
    artists: list[JellyfinArtistSummary] = Field(default_factory=list)
    tracks: list[JellyfinTrackInfo] = Field(default_factory=list)


class JellyfinPaginatedResponse(BaseModel):
    items: list[JellyfinAlbumSummary] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50

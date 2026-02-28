from infrastructure.msgspec_fastapi import AppStruct


class JellyfinTrackInfo(AppStruct):
    jellyfin_id: str
    title: str
    track_number: int
    duration_seconds: float
    album_name: str = ""
    artist_name: str = ""
    codec: str | None = None
    bitrate: int | None = None


class JellyfinAlbumSummary(AppStruct):
    jellyfin_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    musicbrainz_id: str | None = None
    artist_musicbrainz_id: str | None = None


class JellyfinAlbumDetail(AppStruct):
    jellyfin_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    musicbrainz_id: str | None = None
    artist_musicbrainz_id: str | None = None
    tracks: list[JellyfinTrackInfo] = []


class JellyfinAlbumMatch(AppStruct):
    found: bool
    jellyfin_album_id: str | None = None
    tracks: list[JellyfinTrackInfo] = []


class JellyfinArtistSummary(AppStruct):
    jellyfin_id: str
    name: str
    image_url: str | None = None
    album_count: int = 0
    musicbrainz_id: str | None = None


class JellyfinLibraryStats(AppStruct):
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0


class JellyfinSearchResponse(AppStruct):
    albums: list[JellyfinAlbumSummary] = []
    artists: list[JellyfinArtistSummary] = []
    tracks: list[JellyfinTrackInfo] = []


class JellyfinPaginatedResponse(AppStruct):
    items: list[JellyfinAlbumSummary] = []
    total: int = 0
    offset: int = 0
    limit: int = 50

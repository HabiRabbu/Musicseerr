from infrastructure.validators import sanitize_optional_string
from infrastructure.msgspec_fastapi import AppStruct


class LibraryAlbum(AppStruct, rename={"musicbrainz_id": "foreignAlbumId"}):
    artist: str
    album: str
    monitored: bool
    year: int | None = None
    quality: str | None = None
    cover_url: str | None = None
    musicbrainz_id: str | None = None
    artist_mbid: str | None = None
    date_added: int | None = None

    def __post_init__(self) -> None:
        self.cover_url = sanitize_optional_string(self.cover_url)
        self.quality = sanitize_optional_string(self.quality)
        self.musicbrainz_id = sanitize_optional_string(self.musicbrainz_id)
        self.artist_mbid = sanitize_optional_string(self.artist_mbid)


class LibraryArtist(AppStruct):
    mbid: str
    name: str
    album_count: int = 0
    date_added: int | None = None


class LibraryResponse(AppStruct):
    library: list[LibraryAlbum]


class LibraryArtistsResponse(AppStruct):
    artists: list[LibraryArtist]
    total: int


class LibraryAlbumsResponse(AppStruct):
    albums: list[LibraryAlbum]
    total: int


class RecentlyAddedResponse(AppStruct):
    albums: list[LibraryAlbum] = []
    artists: list[LibraryArtist] = []


class LibraryStatsResponse(AppStruct):
    artist_count: int
    album_count: int
    db_size_bytes: int
    db_size_mb: float
    last_sync: int | None = None


class AlbumRemoveResponse(AppStruct):
    success: bool
    artist_removed: bool = False
    artist_name: str | None = None


class AlbumRemovePreviewResponse(AppStruct):
    success: bool
    artist_will_be_removed: bool = False
    artist_name: str | None = None


class SyncLibraryResponse(AppStruct):
    status: str
    artists: int
    albums: int


class LibraryMbidsResponse(AppStruct):
    mbids: list[str] = []
    requested_mbids: list[str] = []


class LibraryGroupedAlbum(AppStruct):
    title: str | None = None
    year: int | None = None
    monitored: bool = False
    cover_url: str | None = None


class LibraryGroupedArtist(AppStruct):
    artist: str
    albums: list[LibraryGroupedAlbum] = []


class LibraryGroupedResponse(AppStruct):
    library: list[LibraryGroupedArtist] = []

from models.library import LibraryAlbum as LibraryAlbum
from models.library import LibraryGroupedAlbum as LibraryGroupedAlbum
from models.library import LibraryGroupedArtist as LibraryGroupedArtist
from infrastructure.msgspec_fastapi import AppStruct


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


class PaginatedLibraryAlbumsResponse(AppStruct):
    albums: list[LibraryAlbum] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


class PaginatedLibraryArtistsResponse(AppStruct):
    artists: list[LibraryArtist] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


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
    monitored_mbids: list[str] = []


class LibraryGroupedResponse(AppStruct):
    library: list[LibraryGroupedArtist] = []


class TrackResolveItem(AppStruct):
    release_group_mbid: str | None = None
    disc_number: int | None = None
    track_number: int | None = None


class TrackResolveRequest(AppStruct):
    items: list[TrackResolveItem] = []


class ResolvedTrack(AppStruct):
    release_group_mbid: str | None = None
    disc_number: int | None = None
    track_number: int | None = None
    source: str | None = None
    track_source_id: str | None = None
    stream_url: str | None = None
    format: str | None = None
    duration: float | None = None


class TrackResolveResponse(AppStruct):
    items: list[ResolvedTrack] = []

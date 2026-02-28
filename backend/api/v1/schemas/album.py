from api.v1.schemas.common import LastFmTagSchema
from infrastructure.msgspec_fastapi import AppStruct


class Track(AppStruct):
    position: int
    title: str
    length: int | None = None
    recording_id: str | None = None


class AlbumInfo(AppStruct):
    title: str
    musicbrainz_id: str
    artist_name: str
    artist_id: str
    release_date: str | None = None
    year: int | None = None
    type: str | None = None
    label: str | None = None
    barcode: str | None = None
    country: str | None = None
    disambiguation: str | None = None
    tracks: list[Track] = []
    total_tracks: int = 0
    total_length: int | None = None
    in_library: bool = False
    requested: bool = False
    cover_url: str | None = None


class AlbumBasicInfo(AppStruct):
    """Minimal album info for fast initial load - no tracks."""
    title: str
    musicbrainz_id: str
    artist_name: str
    artist_id: str
    release_date: str | None = None
    year: int | None = None
    type: str | None = None
    disambiguation: str | None = None
    in_library: bool = False
    requested: bool = False
    cover_url: str | None = None


class AlbumTracksInfo(AppStruct):
    """Track list and extended details - loaded asynchronously."""
    tracks: list[Track] = []
    total_tracks: int = 0
    total_length: int | None = None
    label: str | None = None
    barcode: str | None = None
    country: str | None = None


class LastFmAlbumEnrichment(AppStruct):
    summary: str | None = None
    tags: list[LastFmTagSchema] = []
    listeners: int = 0
    playcount: int = 0
    url: str | None = None

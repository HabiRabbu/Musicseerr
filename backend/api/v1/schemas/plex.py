from __future__ import annotations

from infrastructure.msgspec_fastapi import AppStruct


class PlexTrackInfo(AppStruct):
    plex_id: str
    title: str
    track_number: int
    duration_seconds: float
    disc_number: int = 1
    album_name: str = ""
    artist_name: str = ""
    codec: str | None = None
    bitrate: int | None = None
    part_key: str | None = None


class PlexAlbumSummary(AppStruct):
    plex_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    musicbrainz_id: str | None = None
    artist_musicbrainz_id: str | None = None


class PlexAlbumDetail(AppStruct):
    plex_id: str
    name: str
    artist_name: str = ""
    year: int | None = None
    track_count: int = 0
    image_url: str | None = None
    musicbrainz_id: str | None = None
    artist_musicbrainz_id: str | None = None
    tracks: list[PlexTrackInfo] = []
    genres: list[str] = []


class PlexAlbumMatch(AppStruct):
    found: bool
    plex_album_id: str | None = None
    tracks: list[PlexTrackInfo] = []


class PlexArtistSummary(AppStruct):
    plex_id: str
    name: str
    image_url: str | None = None
    musicbrainz_id: str | None = None


class PlexLibraryStats(AppStruct):
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0


class PlexSearchResponse(AppStruct):
    albums: list[PlexAlbumSummary] = []
    artists: list[PlexArtistSummary] = []
    tracks: list[PlexTrackInfo] = []


class PlexAlbumPage(AppStruct):
    items: list[PlexAlbumSummary] = []
    total: int = 0


class PlexLibrarySectionInfo(AppStruct):
    key: str
    title: str

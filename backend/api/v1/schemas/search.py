from typing import Literal

from infrastructure.msgspec_fastapi import AppStruct

EnrichmentSource = Literal["listenbrainz", "lastfm", "none"]


class SearchResult(AppStruct):
    type: str
    title: str
    musicbrainz_id: str
    artist: str | None = None
    year: int | None = None
    in_library: bool = False
    requested: bool = False
    cover_url: str | None = None
    disambiguation: str | None = None
    type_info: str | None = None
    score: int = 0


class SearchResponse(AppStruct):
    artists: list[SearchResult] = []
    albums: list[SearchResult] = []


class SearchBucketResponse(AppStruct):
    bucket: str
    limit: int
    offset: int
    results: list[SearchResult] = []


class ArtistEnrichment(AppStruct):
    musicbrainz_id: str
    release_group_count: int | None = None
    listen_count: int | None = None


class AlbumEnrichment(AppStruct):
    musicbrainz_id: str
    track_count: int | None = None
    listen_count: int | None = None


class ArtistEnrichmentRequest(AppStruct):
    musicbrainz_id: str
    name: str = ""


class AlbumEnrichmentRequest(AppStruct):
    musicbrainz_id: str
    artist_name: str = ""
    album_name: str = ""


class EnrichmentBatchRequest(AppStruct):
    artists: list[ArtistEnrichmentRequest] = []
    albums: list[AlbumEnrichmentRequest] = []


class EnrichmentResponse(AppStruct):
    artists: list[ArtistEnrichment] = []
    albums: list[AlbumEnrichment] = []
    source: EnrichmentSource = "none"


class SuggestResult(AppStruct):
    type: Literal["artist", "album"]
    title: str
    musicbrainz_id: str
    artist: str | None = None
    year: int | None = None
    in_library: bool = False
    requested: bool = False
    disambiguation: str | None = None
    score: int = 0


class SuggestResponse(AppStruct):
    results: list[SuggestResult] = []

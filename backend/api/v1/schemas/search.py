from typing import Literal, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    type: str
    title: str
    artist: Optional[str] = None
    year: Optional[int] = None
    musicbrainz_id: str
    in_library: bool = False
    requested: bool = False
    cover_url: Optional[str] = None
    disambiguation: Optional[str] = None
    type_info: Optional[str] = None
    score: int = 0


class SearchResponse(BaseModel):
    artists: list[SearchResult] = Field(default_factory=list)
    albums: list[SearchResult] = Field(default_factory=list)


class ArtistEnrichment(BaseModel):
    musicbrainz_id: str
    release_group_count: Optional[int] = None
    listen_count: Optional[int] = None


class AlbumEnrichment(BaseModel):
    musicbrainz_id: str
    track_count: Optional[int] = None
    listen_count: Optional[int] = None


class EnrichmentResponse(BaseModel):
    artists: list[ArtistEnrichment] = Field(default_factory=list)
    albums: list[AlbumEnrichment] = Field(default_factory=list)
    listenbrainz_enabled: bool = False


class SuggestResult(BaseModel):
    type: Literal["artist", "album"]
    title: str
    artist: Optional[str] = None
    year: Optional[int] = None
    musicbrainz_id: str
    in_library: bool = False
    requested: bool = False
    disambiguation: Optional[str] = None
    score: int = 0


class SuggestResponse(BaseModel):
    results: list[SuggestResult] = Field(default_factory=list)

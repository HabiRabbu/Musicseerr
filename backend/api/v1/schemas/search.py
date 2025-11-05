from typing import Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    type: str
    title: str
    artist: Optional[str] = None
    year: Optional[int] = None
    musicbrainz_id: str
    in_library: bool = False
    cover_url: Optional[str] = None


class SearchResponse(BaseModel):
    artists: list[SearchResult] = Field(default_factory=list)
    albums: list[SearchResult] = Field(default_factory=list)

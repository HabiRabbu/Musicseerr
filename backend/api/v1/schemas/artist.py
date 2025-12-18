from typing import Optional
from pydantic import BaseModel, Field


class ExternalLink(BaseModel):
    type: str
    url: str
    label: str


class ArtistInfo(BaseModel):
    name: str
    musicbrainz_id: str
    disambiguation: Optional[str] = None
    type: Optional[str] = None
    country: Optional[str] = None
    life_span: Optional[dict[str, Optional[str]]] = None
    description: Optional[str] = None
    image: Optional[str] = None
    fanart_url: Optional[str] = None
    banner_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    external_links: list[ExternalLink] = Field(default_factory=list)
    in_library: bool = False
    albums: list[dict] = Field(default_factory=list)
    singles: list[dict] = Field(default_factory=list)
    eps: list[dict] = Field(default_factory=list)
    release_group_count: int = 0


class ArtistExtendedInfo(BaseModel):
    description: Optional[str] = None
    image: Optional[str] = None


class ArtistReleases(BaseModel):
    albums: list[dict] = Field(default_factory=list)
    singles: list[dict] = Field(default_factory=list)
    eps: list[dict] = Field(default_factory=list)
    total_count: int = 0
    has_more: bool = False

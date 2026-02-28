from api.v1.schemas.common import LastFmTagSchema
from infrastructure.msgspec_fastapi import AppStruct


class ExternalLink(AppStruct):
    type: str
    url: str
    label: str
    category: str = "other"


class LifeSpan(AppStruct):
    begin: str | None = None
    end: str | None = None
    ended: str | None = None


class ReleaseItem(AppStruct):
    id: str | None = None
    title: str | None = None
    type: str | None = None
    first_release_date: str | None = None
    year: int | None = None
    in_library: bool = False
    requested: bool = False


class ArtistInfo(AppStruct):
    name: str
    musicbrainz_id: str
    disambiguation: str | None = None
    type: str | None = None
    country: str | None = None
    life_span: LifeSpan | None = None
    description: str | None = None
    image: str | None = None
    fanart_url: str | None = None
    banner_url: str | None = None
    tags: list[str] = []
    aliases: list[str] = []
    external_links: list[ExternalLink] = []
    in_library: bool = False
    albums: list[ReleaseItem] = []
    singles: list[ReleaseItem] = []
    eps: list[ReleaseItem] = []
    release_group_count: int = 0


class ArtistExtendedInfo(AppStruct):
    description: str | None = None
    image: str | None = None


class ArtistReleases(AppStruct):
    albums: list[ReleaseItem] = []
    singles: list[ReleaseItem] = []
    eps: list[ReleaseItem] = []
    total_count: int = 0
    has_more: bool = False


class LastFmSimilarArtistSchema(AppStruct):
    name: str
    mbid: str | None = None
    match: float = 0.0
    url: str | None = None


class LastFmArtistEnrichment(AppStruct):
    bio: str | None = None
    summary: str | None = None
    tags: list[LastFmTagSchema] = []
    listeners: int = 0
    playcount: int = 0
    similar_artists: list[LastFmSimilarArtistSchema] = []
    url: str | None = None

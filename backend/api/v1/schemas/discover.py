from pydantic import BaseModel, Field
from api.v1.schemas.home import HomeSection, HomeArtist, ServicePrompt, DiscoverPreview


class BecauseYouListenTo(BaseModel):
    seed_artist: str = Field(description="Name of the seed artist")
    seed_artist_mbid: str = Field(description="MusicBrainz ID of the seed artist")
    listen_count: int = Field(default=0, description="User's listen count for this artist")
    section: HomeSection = Field(description="Section of similar artists")


class DiscoverQueueItemLight(BaseModel):
    release_group_mbid: str
    album_name: str
    artist_name: str
    artist_mbid: str
    cover_url: str | None = None
    recommendation_reason: str
    is_wildcard: bool = False
    in_library: bool = False


class DiscoverQueueEnrichment(BaseModel):
    release_date: str | None = None
    country: str | None = None
    tags: list[str] = Field(default_factory=list)
    youtube_url: str | None = None
    youtube_search_url: str = ""
    youtube_search_available: bool = False
    artist_description: str | None = None
    listen_count: int | None = None


class YouTubeSearchResponse(BaseModel):
    video_id: str | None = None
    embed_url: str | None = None
    error: str | None = None


class YouTubeQuotaResponse(BaseModel):
    used: int
    limit: int
    remaining: int
    date: str


class DiscoverQueueResponse(BaseModel):
    items: list[DiscoverQueueItemLight] = Field(default_factory=list)
    queue_id: str = ""


class DiscoverQueueIgnoreRequest(BaseModel):
    release_group_mbid: str
    artist_mbid: str
    release_name: str
    artist_name: str


class DiscoverQueueValidateRequest(BaseModel):
    release_group_mbids: list[str]


class DiscoverQueueValidateResponse(BaseModel):
    in_library: list[str] = Field(default_factory=list)


class DiscoverResponse(BaseModel):
    because_you_listen_to: list[BecauseYouListenTo] = Field(
        default_factory=list,
        description="Personalized sections based on top listened artists"
    )
    discover_queue_enabled: bool = Field(
        default=True, description="Whether discover queue feature is available"
    )
    fresh_releases: HomeSection | None = Field(
        default=None, description="New releases from followed artists"
    )
    missing_essentials: HomeSection | None = Field(
        default=None, description="Popular albums missing from library"
    )
    rediscover: HomeSection | None = Field(
        default=None, description="Artists you used to listen to"
    )
    artists_you_might_like: HomeSection | None = Field(
        default=None, description="Aggregated similar artist recommendations"
    )
    popular_in_your_genres: HomeSection | None = Field(
        default=None, description="Trending artists in your top genres"
    )
    genre_list: HomeSection | None = Field(
        default=None, description="Genre grid for exploration"
    )
    globally_trending: HomeSection | None = Field(
        default=None, description="Sitewide trending artists"
    )
    integration_status: dict[str, bool] = Field(
        default_factory=dict, description="Status of service integrations"
    )
    service_prompts: list[ServicePrompt] = Field(
        default_factory=list, description="Prompts for unconfigured services"
    )
    genre_artists: dict[str, str | None] = Field(
        default_factory=dict, description="Map of genre name to representative artist MBID"
    )
    refreshing: bool = Field(
        default=False, description="Whether a background refresh is in progress"
    )

from pydantic import BaseModel, Field

from api.v1.schemas.discover import YouTubeQuotaResponse

UNSET = "__UNSET__"


class YouTubeLinkGenerateRequest(BaseModel):
    artist_name: str = Field(description="Artist name for YouTube search")
    album_name: str = Field(description="Album name for YouTube search")
    album_id: str = Field(description="MusicBrainz release group ID")
    cover_url: str | None = Field(default=None, description="Album cover art URL")


class YouTubeTrackLink(BaseModel):
    album_id: str
    track_number: int
    track_name: str
    video_id: str
    artist_name: str
    embed_url: str
    created_at: str


class YouTubeLink(BaseModel):
    album_id: str
    video_id: str | None = None
    album_name: str
    artist_name: str
    embed_url: str | None = None
    cover_url: str | None = None
    created_at: str
    is_manual: bool = False
    track_count: int = 0


class YouTubeLinkResponse(BaseModel):
    link: YouTubeLink
    quota: YouTubeQuotaResponse


class YouTubeTrackLinkGenerateRequest(BaseModel):
    album_id: str = Field(description="Album ID for track association")
    album_name: str = Field(description="Album name for display")
    artist_name: str = Field(description="Artist name for YouTube search")
    track_name: str = Field(description="Track name for YouTube search")
    track_number: int = Field(description="Track position in the album")


class TrackInput(BaseModel):
    track_name: str = Field(description="Track name for YouTube search")
    track_number: int = Field(description="Track position in the album")


class YouTubeTrackLinkBatchGenerateRequest(BaseModel):
    album_id: str = Field(description="Album ID for track association")
    album_name: str = Field(description="Album name for display")
    artist_name: str = Field(description="Artist name for YouTube search")
    tracks: list[TrackInput] = Field(description="Tracks to generate links for")


class YouTubeTrackLinkResponse(BaseModel):
    track_link: YouTubeTrackLink
    quota: YouTubeQuotaResponse


class YouTubeTrackLinkBatchResponse(BaseModel):
    track_links: list[YouTubeTrackLink]
    failed: list[dict] = Field(default_factory=list, description="Tracks that failed to generate")
    quota: YouTubeQuotaResponse


class YouTubeManualLinkRequest(BaseModel):
    album_name: str = Field(description="Album/title name")
    artist_name: str = Field(description="Artist name")
    youtube_url: str = Field(description="Full YouTube video URL")
    cover_url: str | None = Field(default=None, description="Cover image URL")
    album_id: str | None = Field(default=None, description="MusicBrainz album ID (optional for freeform)")


class YouTubeLinkUpdateRequest(BaseModel):
    youtube_url: str | None = Field(default=None, description="New YouTube URL")
    album_name: str | None = Field(default=None, description="Updated album name")
    artist_name: str | None = Field(default=None, description="Updated artist name")
    cover_url: str | None = Field(default=UNSET, description="Updated cover URL (null to clear)")

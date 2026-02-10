from pydantic import BaseModel, Field

from api.v1.schemas.discover import YouTubeQuotaResponse


class YouTubeLinkGenerateRequest(BaseModel):
    artist_name: str = Field(description="Artist name for YouTube search")
    album_name: str = Field(description="Album name for YouTube search")
    album_id: str = Field(description="MusicBrainz release group ID")
    cover_url: str | None = Field(default=None, description="Album cover art URL")


class YouTubeLink(BaseModel):
    album_id: str
    video_id: str
    album_name: str
    artist_name: str
    embed_url: str
    cover_url: str | None = None
    created_at: str


class YouTubeLinkResponse(BaseModel):
    link: YouTubeLink
    quota: YouTubeQuotaResponse

import msgspec

from api.v1.schemas.discover import YouTubeQuotaResponse
from infrastructure.msgspec_fastapi import AppStruct


class YouTubeLinkGenerateRequest(AppStruct):
    artist_name: str
    album_name: str
    album_id: str
    cover_url: str | None = None


class YouTubeTrackLink(AppStruct):
    album_id: str
    track_number: int
    track_name: str
    video_id: str
    artist_name: str
    embed_url: str
    created_at: str
    album_name: str = ""


class YouTubeLink(AppStruct):
    album_id: str
    album_name: str
    artist_name: str
    created_at: str
    video_id: str | None = None
    embed_url: str | None = None
    cover_url: str | None = None
    is_manual: bool = False
    track_count: int = 0


class YouTubeLinkResponse(AppStruct):
    link: YouTubeLink
    quota: YouTubeQuotaResponse


class YouTubeTrackLinkGenerateRequest(AppStruct):
    album_id: str
    album_name: str
    artist_name: str
    track_name: str
    track_number: int


class TrackInput(AppStruct):
    track_name: str
    track_number: int


class YouTubeTrackLinkBatchGenerateRequest(AppStruct):
    album_id: str
    album_name: str
    artist_name: str
    tracks: list[TrackInput]


class YouTubeTrackLinkResponse(AppStruct):
    track_link: YouTubeTrackLink
    quota: YouTubeQuotaResponse


class YouTubeTrackLinkFailure(AppStruct):
    track_number: int
    track_name: str
    reason: str


class YouTubeTrackLinkBatchResponse(AppStruct):
    track_links: list[YouTubeTrackLink]
    quota: YouTubeQuotaResponse
    failed: list[YouTubeTrackLinkFailure] = []


class YouTubeManualLinkRequest(AppStruct):
    album_name: str
    artist_name: str
    youtube_url: str
    cover_url: str | None = None
    album_id: str | None = None


class YouTubeLinkUpdateRequest(AppStruct):
    youtube_url: str | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None | msgspec.UnsetType = msgspec.UNSET

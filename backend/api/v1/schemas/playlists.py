import msgspec
from infrastructure.msgspec_fastapi import AppStruct


class PlaylistTrackResponse(AppStruct):
    id: str
    position: int
    track_name: str
    artist_name: str
    album_name: str
    album_id: str | None = None
    artist_id: str | None = None
    track_source_id: str | None = None
    cover_url: str | None = None
    source_type: str = ""
    available_sources: list[str] | None = None
    format: str | None = None
    track_number: int | None = None
    duration: int | None = None
    created_at: str = ""


class PlaylistSummaryResponse(AppStruct):
    id: str
    name: str
    track_count: int = 0
    total_duration: int | None = None
    cover_urls: list[str] = msgspec.field(default_factory=list)
    custom_cover_url: str | None = None
    created_at: str = ""
    updated_at: str = ""


class PlaylistDetailResponse(AppStruct):
    # Frontend PlaylistDetail extends PlaylistSummary — keep fields in sync with PlaylistSummaryResponse
    id: str
    name: str
    cover_urls: list[str] = msgspec.field(default_factory=list)
    custom_cover_url: str | None = None
    tracks: list[PlaylistTrackResponse] = msgspec.field(default_factory=list)
    track_count: int = 0
    total_duration: int | None = None
    created_at: str = ""
    updated_at: str = ""


class PlaylistListResponse(AppStruct):
    playlists: list[PlaylistSummaryResponse] = msgspec.field(default_factory=list)


class CreatePlaylistRequest(AppStruct):
    name: str


class UpdatePlaylistRequest(AppStruct):
    name: str | None = None


class TrackDataRequest(AppStruct):
    track_name: str
    artist_name: str
    album_name: str
    album_id: str | None = None
    artist_id: str | None = None
    track_source_id: str | None = None
    cover_url: str | None = None
    source_type: str = ""
    available_sources: list[str] | None = None
    format: str | None = None
    track_number: int | None = None
    duration: float | int | None = None


class AddTracksRequest(AppStruct):
    tracks: list[TrackDataRequest]
    position: int | None = None


class ReorderTrackRequest(AppStruct):
    track_id: str
    new_position: int


class ReorderTrackResponse(AppStruct):
    status: str = "ok"
    message: str = "Track reordered"
    actual_position: int = 0


class UpdateTrackRequest(AppStruct):
    source_type: str | None = None
    available_sources: list[str] | None = None


class AddTracksResponse(AppStruct):
    tracks: list[PlaylistTrackResponse] = msgspec.field(default_factory=list)


class CoverUploadResponse(AppStruct):
    cover_url: str


class TrackIdentifier(AppStruct):
    track_name: str
    artist_name: str
    album_name: str


class CheckTrackMembershipRequest(AppStruct):
    tracks: list[TrackIdentifier]


class CheckTrackMembershipResponse(AppStruct):
    membership: dict[str, list[int]]


class ResolveSourcesResponse(AppStruct):
    sources: dict[str, list[str]]

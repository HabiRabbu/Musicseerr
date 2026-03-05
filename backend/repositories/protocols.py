from typing import Protocol, Any
import msgspec
from api.v1.schemas.search import SearchResult
from api.v1.schemas.artist import ArtistInfo
from api.v1.schemas.album import AlbumInfo
from api.v1.schemas.library import LibraryAlbum
from api.v1.schemas.request import QueueItem
from api.v1.schemas.common import ServiceStatus
from api.v1.schemas.discover import YouTubeQuotaResponse
from repositories.jellyfin_models import JellyfinItem as JellyfinItem
from repositories.jellyfin_models import PlaybackUrlResult as PlaybackUrlResult
from repositories.jellyfin_models import JellyfinUser as JellyfinUser
from repositories.lastfm_models import (
    LastFmAlbum,
    LastFmAlbumInfo,
    LastFmArtist,
    LastFmArtistInfo,
    LastFmLovedTrack,
    LastFmRecentTrack,
    LastFmSession,
    LastFmSimilarArtist,
    LastFmToken,
    LastFmTrack,
)


class ListenBrainzArtist(msgspec.Struct):
    artist_name: str
    listen_count: int
    artist_mbids: list[str] | None = None


class ListenBrainzReleaseGroup(msgspec.Struct):
    release_group_name: str
    artist_name: str
    listen_count: int
    release_group_mbid: str | None = None
    artist_mbids: list[str] | None = None
    caa_id: int | None = None
    caa_release_mbid: str | None = None


class ListenBrainzFeedbackRecording(msgspec.Struct):
    track_name: str
    artist_name: str
    release_name: str | None = None
    recording_mbid: str | None = None
    release_mbid: str | None = None
    artist_mbids: list[str] | None = None
    score: int = 0


class MusicBrainzRepositoryProtocol(Protocol):

    async def search_artists(
        self,
        query: str,
        limit: int = 10,
        included_types: set[str] | None = None
    ) -> list[SearchResult]:
        ...

    async def search_albums(
        self,
        query: str,
        limit: int = 10,
        included_types: set[str] | None = None,
        included_secondary_types: set[str] | None = None,
        included_statuses: set[str] | None = None
    ) -> list[SearchResult]:
        ...

    async def get_artist_detail(
        self,
        artist_mbid: str,
        included_types: set[str] | None = None,
        included_secondary_types: set[str] | None = None,
        included_statuses: set[str] | None = None
    ) -> ArtistInfo | None:
        ...

    async def get_release_group(
        self,
        release_group_mbid: str
    ) -> AlbumInfo | None:
        ...

    async def get_release(
        self,
        release_mbid: str
    ) -> Any | None:
        ...

    async def get_release_group_id_from_release(
        self,
        release_mbid: str
    ) -> str | None:
        ...

    async def get_release_groups_by_artist(
        self,
        artist_mbid: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        ...


class LidarrRepositoryProtocol(Protocol):

    async def get_library_albums(self) -> list[LibraryAlbum]:
        ...

    async def get_library_album_mbids(self) -> set[str]:
        ...

    async def get_library_artist_mbids(self) -> set[str]:
        ...

    async def add_album(self, album_mbid: str) -> dict[str, Any]:
        ...

    async def get_queue(self) -> list[QueueItem]:
        ...

    async def check_status(self) -> ServiceStatus:
        ...

    async def get_artist_details(self, artist_mbid: str) -> dict[str, Any] | None:
        ...

    async def get_album_details(self, album_mbid: str) -> dict[str, Any] | None:
        ...

    async def get_album_tracks(self, album_id: int) -> list[dict[str, Any]]:
        ...

    async def get_artist_albums(self, artist_mbid: str) -> list[dict[str, Any]]:
        ...

    async def get_artist_mbids(self) -> set[str]:
        ...

    async def get_library_mbids(self, include_release_ids: bool = True) -> set[str]:
        ...

    async def get_requested_mbids(self) -> set[str]:
        ...

    async def delete_album(self, album_id: int, delete_files: bool = False) -> bool:
        ...

    async def delete_artist(self, artist_id: int, delete_files: bool = False) -> bool:
        ...

    async def get_queue_details(
        self, include_artist: bool = True, include_album: bool = True
    ) -> list[dict[str, Any]]:
        ...

    async def remove_queue_item(
        self, queue_id: int, remove_from_client: bool = True
    ) -> bool:
        ...

    async def trigger_album_search(self, album_ids: list[int]) -> dict[str, Any] | None:
        ...

    async def get_history_for_album(
        self,
        album_id: int,
        include_album: bool = True,
        include_artist: bool = True,
    ) -> list[dict[str, Any]]:
        ...

    async def get_track_file(self, track_file_id: int) -> dict[str, Any] | None:
        ...

    async def get_track_files_by_album(self, album_id: int) -> list[dict[str, Any]]:
        ...

    async def get_all_albums(self) -> list[dict[str, Any]]:
        ...


class WikidataRepositoryProtocol(Protocol):

    async def get_artist_bio(self, artist_mbid: str) -> str | None:
        ...

    async def get_artist_image(self, artist_mbid: str) -> str | None:
        ...


class CoverArtRepositoryProtocol(Protocol):

    async def get_cover_url(
        self,
        album_mbid: str,
        size: str = "500"
    ) -> str | None:
        ...

    async def batch_prefetch_covers(
        self,
        album_mbids: list[str],
        size: str = "250"
    ) -> None:
        ...


class ListenBrainzRepositoryProtocol(Protocol):

    async def get_user_loved_recordings(
        self,
        username: str | None = None,
        count: int = 25,
        offset: int = 0,
    ) -> list[ListenBrainzFeedbackRecording]:
        ...

    async def submit_now_playing(
        self,
        artist_name: str,
        track_name: str,
        release_name: str = "",
        duration_ms: int = 0,
    ) -> bool:
        ...

    async def submit_single_listen(
        self,
        artist_name: str,
        track_name: str,
        listened_at: int,
        release_name: str = "",
        duration_ms: int = 0,
    ) -> bool:
        ...

    async def get_trending_artists(
        self,
        time_range: str = "this_week",
        limit: int = 20,
        offset: int = 0
    ) -> list[ListenBrainzArtist]:
        ...

    async def get_popular_release_groups(
        self,
        time_range: str = "this_week",
        limit: int = 20,
        offset: int = 0
    ) -> list[ListenBrainzReleaseGroup]:
        ...

    async def get_fresh_releases(
        self,
        limit: int = 20
    ) -> list[ListenBrainzReleaseGroup]:
        ...

    async def get_similar_artists(
        self,
        artist_mbid: str,
        limit: int = 10
    ) -> list[ListenBrainzArtist]:
        ...

    async def get_artist_top_release_groups(
        self,
        artist_mbid: str,
        count: int = 10
    ) -> list[ListenBrainzReleaseGroup]:
        ...

    async def get_release_group_popularity_batch(
        self,
        release_group_mbids: list[str]
    ) -> dict[str, int]:
        ...


class JellyfinRepositoryProtocol(Protocol):

    # --- Existing methods (implemented in JellyfinRepository) ---

    def is_configured(self) -> bool:
        ...

    def configure(self, base_url: str, api_key: str, user_id: str = "") -> None:
        ...

    async def validate_connection(self) -> tuple[bool, str]:
        ...

    async def get_users(self) -> list[JellyfinUser]:
        ...

    async def fetch_users_direct(self) -> list[JellyfinUser]:
        ...

    async def get_current_user(self) -> JellyfinUser | None:
        ...

    async def get_recently_played(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[JellyfinItem]:
        ...

    async def get_favorite_artists(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[JellyfinItem]:
        ...

    async def get_favorite_albums(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[JellyfinItem]:
        ...

    async def get_most_played_artists(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[JellyfinItem]:
        ...

    async def get_most_played_albums(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[JellyfinItem]:
        ...

    async def get_recently_added(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[JellyfinItem]:
        ...

    async def get_genres(self, user_id: str | None = None) -> list[str]:
        ...

    async def get_artists_by_genre(
        self, genre: str, user_id: str | None = None, limit: int = 50
    ) -> list[JellyfinItem]:
        ...

    def get_image_url(self, item_id: str, image_tag: str | None = None) -> str | None:
        ...

    def get_auth_headers(self) -> dict[str, str]:
        ...

    # --- Library browsing ---

    async def get_albums(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        genre: str | None = None,
    ) -> tuple[list[JellyfinItem], int]:
        ...

    async def get_album_tracks(self, album_id: str) -> list[JellyfinItem]:
        ...

    async def get_album_detail(self, album_id: str) -> JellyfinItem | None:
        ...

    async def get_album_by_mbid(self, musicbrainz_id: str) -> JellyfinItem | None:
        ...

    async def get_artist_by_mbid(self, musicbrainz_id: str) -> JellyfinItem | None:
        ...

    async def get_artists(
        self, limit: int = 50, offset: int = 0
    ) -> list[JellyfinItem]:
        ...

    async def build_mbid_index(self) -> dict[str, str]:
        ...

    async def search_items(
        self,
        query: str,
        item_types: str = "MusicAlbum,Audio,MusicArtist",
    ) -> list[JellyfinItem]:
        ...

    async def get_library_stats(self) -> dict[str, Any]:
        ...

    # --- Streaming & playback reporting ---

    async def get_playback_url(self, item_id: str) -> PlaybackUrlResult:
        ...

    async def get_playback_info(self, item_id: str) -> dict[str, Any]:
        ...

    async def report_playback_start(
        self, item_id: str, play_session_id: str, play_method: str = "Transcode"
    ) -> None:
        ...

    async def report_playback_progress(
        self,
        item_id: str,
        play_session_id: str,
        position_ticks: int,
        is_paused: bool,
    ) -> None:
        ...

    async def report_playback_stopped(
        self, item_id: str, play_session_id: str, position_ticks: int
    ) -> None:
        ...


class LastFmRepositoryProtocol(Protocol):

    def configure(self, api_key: str, shared_secret: str, session_key: str = "") -> None:
        ...

    @staticmethod
    def reset_circuit_breaker() -> None:
        ...

    async def get_token(self) -> LastFmToken:
        ...

    async def get_session(self, token: str) -> LastFmSession:
        ...

    async def validate_api_key(self) -> tuple[bool, str]:
        ...

    async def validate_session(self) -> tuple[bool, str]:
        ...

    async def update_now_playing(
        self,
        artist: str,
        track: str,
        album: str = "",
        duration: int = 0,
        mbid: str | None = None,
    ) -> bool:
        ...

    async def scrobble(
        self,
        artist: str,
        track: str,
        timestamp: int,
        album: str = "",
        duration: int = 0,
        mbid: str | None = None,
    ) -> bool:
        ...

    async def get_user_top_artists(
        self, username: str, period: str = "overall", limit: int = 50
    ) -> list[LastFmArtist]:
        ...

    async def get_user_top_albums(
        self, username: str, period: str = "overall", limit: int = 50
    ) -> list[LastFmAlbum]:
        ...

    async def get_user_top_tracks(
        self, username: str, period: str = "overall", limit: int = 50
    ) -> list[LastFmTrack]:
        ...

    async def get_user_recent_tracks(
        self, username: str, limit: int = 50
    ) -> list[LastFmRecentTrack]:
        ...

    async def get_user_loved_tracks(
        self, username: str, limit: int = 50
    ) -> list[LastFmLovedTrack]:
        ...

    async def get_user_weekly_artist_chart(
        self, username: str
    ) -> list[LastFmArtist]:
        ...

    async def get_user_weekly_album_chart(
        self, username: str
    ) -> list[LastFmAlbum]:
        ...

    async def get_artist_top_tracks(
        self, artist: str, mbid: str | None = None, limit: int = 10
    ) -> list[LastFmTrack]:
        ...

    async def get_artist_top_albums(
        self, artist: str, mbid: str | None = None, limit: int = 10
    ) -> list[LastFmAlbum]:
        ...

    async def get_artist_info(
        self, artist: str, mbid: str | None = None, username: str | None = None
    ) -> LastFmArtistInfo | None:
        ...

    async def get_album_info(
        self,
        artist: str,
        album: str,
        mbid: str | None = None,
        username: str | None = None,
    ) -> LastFmAlbumInfo | None:
        ...

    async def get_similar_artists(
        self, artist: str, mbid: str | None = None, limit: int = 30
    ) -> list[LastFmSimilarArtist]:
        ...

    async def get_global_top_artists(self, limit: int = 50) -> list[LastFmArtist]:
        ...

    async def get_global_top_tracks(self, limit: int = 50) -> list[LastFmTrack]:
        ...

    async def get_tag_top_artists(
        self, tag: str, limit: int = 50
    ) -> list[LastFmArtist]:
        ...


class YouTubeRepositoryProtocol(Protocol):

    @property
    def is_configured(self) -> bool:
        ...

    async def search_video(self, artist: str, album: str) -> str | None:
        ...

    def get_quota_status(self) -> YouTubeQuotaResponse:
        ...

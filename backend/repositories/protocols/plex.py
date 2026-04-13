from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING

from repositories.plex_models import (
    PlexAlbum,
    PlexArtist,
    PlexHistoryEntry,
    PlexLibrarySection,
    PlexOAuthPin,
    PlexPlaylist,
    PlexSession,
    PlexTrack,
)

if TYPE_CHECKING:
    from repositories.plex_models import StreamProxyResult


class PlexRepositoryProtocol(Protocol):

    def is_configured(self) -> bool:
        ...

    def configure(self, url: str, token: str, client_id: str = "") -> None:
        ...

    async def ping(self) -> bool:
        ...

    async def get_libraries(self) -> list[PlexLibrarySection]:
        ...

    async def get_music_libraries(self) -> list[PlexLibrarySection]:
        ...

    async def get_artists(
        self, section_id: str, size: int = 100, offset: int = 0
    ) -> list[PlexArtist]:
        ...

    async def get_albums(
        self,
        section_id: str,
        size: int = 50,
        offset: int = 0,
        sort: str = "titleSort:asc",
        genre: str | None = None,
        mood: str | None = None,
        decade: str | None = None,
    ) -> tuple[list[PlexAlbum], int]:
        ...

    async def get_track_count(self, section_id: str) -> int:
        ...

    async def get_artist_count(self, section_id: str) -> int:
        ...

    async def get_album_tracks(self, rating_key: str) -> list[PlexTrack]:
        ...

    async def get_album_metadata(self, rating_key: str) -> PlexAlbum:
        ...

    async def get_recently_added(
        self, section_id: str, limit: int = 20
    ) -> list[PlexAlbum]:
        ...

    async def get_recently_viewed(
        self, section_id: str, limit: int = 20
    ) -> list[PlexAlbum]:
        ...

    async def get_playlists(self) -> list[PlexPlaylist]:
        ...

    async def get_playlist_items(self, rating_key: str) -> list[PlexTrack]:
        ...

    async def search(
        self,
        query: str,
        section_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, list[Any]]:
        ...

    async def get_genres(self, section_id: str) -> list[str]:
        ...

    async def get_moods(self, section_id: str) -> list[str]:
        ...

    async def get_hubs(
        self, section_id: str, count: int = 10
    ) -> list[dict[str, Any]]:
        ...

    async def scrobble(self, rating_key: str) -> bool:
        ...

    async def now_playing(self, rating_key: str, state: str = "playing") -> bool:
        ...

    def build_stream_url(self, track: PlexTrack) -> str:
        ...

    async def proxy_head_stream(self, part_key: str) -> StreamProxyResult:
        ...

    async def proxy_get_stream(
        self, part_key: str, range_header: str | None = None
    ) -> StreamProxyResult:
        ...

    async def proxy_thumb(self, rating_key: str, size: int = 500) -> tuple[bytes, str]:
        ...

    async def proxy_playlist_composite(self, rating_key: str, size: int = 500) -> tuple[bytes, str]:
        ...

    async def validate_connection(self) -> tuple[bool, str]:
        ...

    async def create_oauth_pin(self, client_id: str) -> PlexOAuthPin:
        ...

    async def poll_oauth_pin(self, pin_id: int, client_id: str) -> str | None:
        ...

    async def clear_cache(self) -> None:
        ...

    @property
    def stats_ttl(self) -> int:
        ...

    def configure_cache_ttls(
        self,
        *,
        list_ttl: int | None = None,
        search_ttl: int | None = None,
        genres_ttl: int | None = None,
        detail_ttl: int | None = None,
        stats_ttl: int | None = None,
    ) -> None:
        ...

    async def get_sessions(self) -> list[PlexSession]:
        ...

    async def get_listening_history(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[PlexHistoryEntry], int]:
        ...

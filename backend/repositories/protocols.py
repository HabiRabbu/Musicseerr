from typing import Protocol, Optional, Any
from api.v1.schemas.search import SearchResult
from api.v1.schemas.artist import ArtistInfo
from api.v1.schemas.album import AlbumInfo
from api.v1.schemas.library import LibraryAlbum
from api.v1.schemas.request import QueueItem
from api.v1.schemas.common import ServiceStatus
from dataclasses import dataclass


@dataclass
class ListenBrainzArtist:
    artist_name: str
    listen_count: int
    artist_mbids: list[str] | None = None


@dataclass
class ListenBrainzReleaseGroup:
    release_group_name: str
    artist_name: str
    listen_count: int
    release_group_mbid: str | None = None
    artist_mbids: list[str] | None = None
    caa_id: int | None = None
    caa_release_mbid: str | None = None


@dataclass
class JellyfinItem:
    id: str
    name: str
    type: str
    artist_name: str | None = None
    album_name: str | None = None
    play_count: int = 0
    is_favorite: bool = False
    last_played: str | None = None
    image_tag: str | None = None
    parent_id: str | None = None
    album_id: str | None = None
    artist_id: str | None = None
    provider_ids: dict[str, str] | None = None


class MusicBrainzRepositoryProtocol(Protocol):
    
    async def search_artists(
        self,
        query: str,
        limit: int = 10,
        included_types: Optional[set[str]] = None
    ) -> list[SearchResult]:
        ...
    
    async def search_albums(
        self,
        query: str,
        limit: int = 10,
        included_types: Optional[set[str]] = None,
        included_secondary_types: Optional[set[str]] = None,
        included_statuses: Optional[set[str]] = None
    ) -> list[SearchResult]:
        ...
    
    async def get_artist_detail(
        self,
        artist_mbid: str,
        included_types: Optional[set[str]] = None,
        included_secondary_types: Optional[set[str]] = None,
        included_statuses: Optional[set[str]] = None
    ) -> Optional[ArtistInfo]:
        ...
    
    async def get_release_group(
        self,
        release_group_mbid: str
    ) -> Optional[AlbumInfo]:
        ...
    
    async def get_release(
        self,
        release_mbid: str
    ) -> Optional[Any]:
        ...
    
    async def get_release_group_id_from_release(
        self,
        release_mbid: str
    ) -> Optional[str]:
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
    
    async def get_artist_details(self, artist_mbid: str) -> Optional[dict[str, Any]]:
        ...
    
    async def get_album_details(self, album_mbid: str) -> Optional[dict[str, Any]]:
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


class WikidataRepositoryProtocol(Protocol):
    
    async def get_artist_bio(self, artist_mbid: str) -> Optional[str]:
        ...
    
    async def get_artist_image(self, artist_mbid: str) -> Optional[str]:
        ...


class CoverArtRepositoryProtocol(Protocol):
    
    async def get_cover_url(
        self,
        album_mbid: str,
        size: str = "500"
    ) -> Optional[str]:
        ...
    
    async def batch_prefetch_covers(
        self,
        album_mbids: list[str],
        size: str = "250"
    ) -> None:
        ...


class ListenBrainzRepositoryProtocol(Protocol):
    
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
    
    async def check_connection(self) -> ServiceStatus:
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
    
    def is_configured(self) -> bool:
        ...
    
    async def get_recently_played(
        self,
        limit: int = 20
    ) -> list[JellyfinItem]:
        ...
    
    async def get_favorites(
        self,
        item_type: str = "MusicArtist",
        limit: int = 20
    ) -> list[JellyfinItem]:
        ...
    
    async def check_connection(self) -> ServiceStatus:
        ...


class YouTubeRepositoryProtocol(Protocol):

    @property
    def is_configured(self) -> bool:
        ...

    async def search_video(self, artist: str, album: str) -> str | None:
        ...

    def get_quota_status(self) -> dict:
        ...

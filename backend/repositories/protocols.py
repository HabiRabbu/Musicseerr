from typing import Protocol, Optional, Any
from api.v1.schemas.search import SearchResult
from api.v1.schemas.artist import ArtistInfo
from api.v1.schemas.album import AlbumInfo
from api.v1.schemas.library import LibraryAlbum
from api.v1.schemas.request import QueueItem
from api.v1.schemas.common import ServiceStatus


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

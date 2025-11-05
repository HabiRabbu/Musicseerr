"""
Protocol interfaces for repositories.

These protocols define the contracts that repository implementations must follow,
supporting the Dependency Inversion Principle (SOLID).
"""
from typing import Protocol, Optional, Any
from api.v1.schemas.search import SearchResult
from api.v1.schemas.artist import ArtistInfo
from api.v1.schemas.album import AlbumInfo
from api.v1.schemas.library import LibraryAlbum
from api.v1.schemas.request import QueueItem
from api.v1.schemas.common import ServiceStatus


class MusicBrainzRepositoryProtocol(Protocol):
    """Protocol for MusicBrainz data access."""
    
    async def search_artists(
        self,
        query: str,
        limit: int = 10,
        included_types: Optional[set[str]] = None
    ) -> list[SearchResult]:
        """Search for artists by name."""
        ...
    
    async def search_albums(
        self,
        query: str,
        limit: int = 10,
        included_types: Optional[set[str]] = None,
        included_secondary_types: Optional[set[str]] = None,
        included_statuses: Optional[set[str]] = None
    ) -> list[SearchResult]:
        """Search for albums (release groups)."""
        ...
    
    async def get_artist_detail(
        self,
        artist_mbid: str,
        included_types: Optional[set[str]] = None,
        included_secondary_types: Optional[set[str]] = None,
        included_statuses: Optional[set[str]] = None
    ) -> Optional[ArtistInfo]:
        """Get detailed artist information."""
        ...
    
    async def get_release_group(
        self,
        release_group_mbid: str
    ) -> Optional[AlbumInfo]:
        """Get release group (album) details."""
        ...
    
    async def get_release(
        self,
        release_mbid: str
    ) -> Optional[Any]:
        """Get specific release details."""
        ...


class LidarrRepositoryProtocol(Protocol):
    """Protocol for Lidarr integration."""
    
    async def get_library_albums(self) -> list[LibraryAlbum]:
        """Get all albums in Lidarr library."""
        ...
    
    async def get_library_album_mbids(self) -> set[str]:
        """Get MBIDs of all albums in library."""
        ...
    
    async def get_library_artist_mbids(self) -> set[str]:
        """Get MBIDs of all artists in library."""
        ...
    
    async def add_album(self, album_mbid: str) -> dict[str, Any]:
        """Add album to Lidarr by MBID."""
        ...
    
    async def get_queue(self) -> list[QueueItem]:
        """Get current download queue."""
        ...
    
    async def check_status(self) -> ServiceStatus:
        """Check Lidarr service health."""
        ...


class WikidataRepositoryProtocol(Protocol):
    """Protocol for Wikidata integration."""
    
    async def get_artist_bio(self, artist_mbid: str) -> Optional[str]:
        """Get artist biography from Wikidata."""
        ...
    
    async def get_artist_image(self, artist_mbid: str) -> Optional[str]:
        """Get artist image URL from Wikidata."""
        ...


class CoverArtRepositoryProtocol(Protocol):
    """Protocol for Cover Art Archive integration."""
    
    async def get_cover_url(
        self,
        album_mbid: str,
        size: str = "500"
    ) -> Optional[str]:
        """Get cover art URL for an album."""
        ...
    
    async def batch_prefetch_covers(
        self,
        album_mbids: list[str],
        size: str = "250"
    ) -> None:
        """Prefetch multiple covers into cache."""
        ...

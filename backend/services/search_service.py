import asyncio
import logging
from typing import Optional
from api.v1.schemas.search import SearchResult, SearchResponse
from repositories.protocols import MusicBrainzRepositoryProtocol, LidarrRepositoryProtocol, CoverArtRepositoryProtocol
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

COVER_PREFETCH_LIMIT = 12


class SearchService:
    def __init__(
        self,
        mb_repo: MusicBrainzRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        coverart_repo: CoverArtRepositoryProtocol,
        preferences_service: PreferencesService
    ):
        self._mb_repo = mb_repo
        self._lidarr_repo = lidarr_repo
        self._coverart_repo = coverart_repo
        self._preferences_service = preferences_service
    
    async def _safe_gather(self, *tasks):
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r if not isinstance(r, Exception) else None for r in results]
    
    async def search(
        self,
        query: str,
        limit_artists: int = 10,
        limit_albums: int = 10,
        buckets: Optional[list[str]] = None
    ) -> SearchResponse:
        prefs = self._preferences_service.get_preferences()
        included_secondary_types = set(t.lower() for t in prefs.secondary_types)
        
        limits = {}
        if not buckets or "artists" in buckets:
            limits["artists"] = limit_artists
        if not buckets or "albums" in buckets:
            limits["albums"] = limit_albums
        
        try:
            grouped = await self._mb_repo.search_grouped(
                query,
                limits=limits,
                buckets=buckets,
                included_secondary_types=included_secondary_types
            )
        except Exception as e:
            logger.error(f"MusicBrainz search failed: {e}")
            grouped = {"artists": [], "albums": []}
        
        grouped = grouped or {"artists": [], "albums": []}
        
        try:
            library_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
        except Exception as e:
            logger.error(f"Lidarr library fetch failed: {e}")
            library_mbids = set()
        
        library_mbids = library_mbids or set()
        
        for item in grouped.get("albums", []):
            item.in_library = (item.musicbrainz_id or "").lower() in library_mbids
        
        return SearchResponse(
            artists=grouped.get("artists", []),
            albums=grouped.get("albums", [])
        )
    
    def schedule_cover_prefetch(self, albums: list[SearchResult]) -> list[str]:
        return [
            item.musicbrainz_id
            for item in albums[:COVER_PREFETCH_LIMIT]
            if item.musicbrainz_id
        ]
    
    async def search_bucket(
        self,
        bucket: str,
        query: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[SearchResult]:
        prefs = self._preferences_service.get_preferences()
        included_secondary_types = set(t.lower() for t in prefs.secondary_types)
        
        if bucket == "artists":
            results = await self._mb_repo.search_artists(query, limit=limit, offset=offset)
        elif bucket == "albums":
            results = await self._mb_repo.search_albums(
                query,
                limit=limit,
                offset=offset,
                included_secondary_types=included_secondary_types
            )
        else:
            return []
        
        if bucket == "albums":
            library_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
            for item in results:
                item.in_library = (item.musicbrainz_id or "").lower() in library_mbids
        
        return results

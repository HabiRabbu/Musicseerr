import asyncio
import logging
from math import ceil
from typing import Optional
from api.v1.schemas.search import SearchResult, SearchResponse, SuggestResult, SuggestResponse
from repositories.protocols import MusicBrainzRepositoryProtocol, LidarrRepositoryProtocol, CoverArtRepositoryProtocol
from services.preferences_service import PreferencesService
from infrastructure.http.deduplication import deduplicate

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

    @deduplicate(lambda self, query, limit_artists=10, limit_albums=10, buckets=None: f"search:{query}:{limit_artists}:{limit_albums}:{buckets}")
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

        try:
            queue_items = await self._lidarr_repo.get_queue()
            queued_mbids = {item.musicbrainz_id.lower() for item in queue_items if item.musicbrainz_id}
        except Exception as e:
            logger.warning(f"Failed to fetch queue: {e}")
            queued_mbids = set()

        for item in grouped.get("albums", []):
            mbid_lower = (item.musicbrainz_id or "").lower()
            item.in_library = mbid_lower in library_mbids
            item.requested = mbid_lower in queued_mbids and not item.in_library

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

    @deduplicate(lambda self, bucket, query, limit=50, offset=0: f"search_bucket:{bucket}:{query}:{limit}:{offset}")
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
            try:
                queue_items = await self._lidarr_repo.get_queue()
                queued_mbids = {item.musicbrainz_id.lower() for item in queue_items if item.musicbrainz_id}
            except Exception as e:
                logger.warning(f"Failed to fetch queue: {e}")
                queued_mbids = set()

            for item in results:
                mbid_lower = (item.musicbrainz_id or "").lower()
                item.in_library = mbid_lower in library_mbids
                item.requested = mbid_lower in queued_mbids and not item.in_library

        return results

    @deduplicate(lambda self, query, limit=5: f"suggest:{query.strip().lower()}:{limit}")
    async def suggest(self, query: str, limit: int = 5) -> SuggestResponse:
        query = query.strip()
        if len(query) < 2:
            return SuggestResponse()

        prefs = self._preferences_service.get_preferences()
        included_secondary_types = set(t.lower() for t in prefs.secondary_types)
        bucket_limit = ceil(limit * 0.6)

        try:
            grouped = await self._mb_repo.search_grouped(
                query,
                limits={"artists": bucket_limit, "albums": bucket_limit},
                included_secondary_types=included_secondary_types,
            )
        except Exception as e:
            logger.warning("MusicBrainz suggest failed (query_len=%d): %s", len(query), type(e).__name__)
            return SuggestResponse()

        grouped = grouped or {"artists": [], "albums": []}

        try:
            library_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
        except Exception as e:
            logger.warning("Lidarr library fetch failed during suggest: %s", type(e).__name__)
            library_mbids = set()
        library_mbids = library_mbids or set()

        try:
            queue_items = await self._lidarr_repo.get_queue()
            queued_mbids = {item.musicbrainz_id.lower() for item in queue_items if item.musicbrainz_id}
        except Exception as e:
            logger.warning("Lidarr queue fetch failed during suggest: %s", type(e).__name__)
            queued_mbids = set()

        for item in grouped.get("albums", []):
            mbid_lower = (item.musicbrainz_id or "").lower()
            item.in_library = mbid_lower in library_mbids
            item.requested = mbid_lower in queued_mbids and not item.in_library

        suggestions: list[SuggestResult] = []
        for item in grouped.get("artists", []) + grouped.get("albums", []):
            suggestions.append(SuggestResult(
                type=item.type,
                title=item.title,
                artist=item.artist,
                year=item.year,
                musicbrainz_id=item.musicbrainz_id,
                in_library=item.in_library,
                requested=item.requested,
                disambiguation=item.disambiguation,
                score=item.score,
            ))

        type_order = {"artist": 0, "album": 1}
        suggestions.sort(key=lambda s: (-s.score, type_order.get(s.type, 2), s.title.lower()))
        return SuggestResponse(results=suggestions[:limit])

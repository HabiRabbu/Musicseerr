import asyncio
import logging
from typing import Any, Optional
import musicbrainzngs
from api.v1.schemas.search import SearchResult
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import (
    mb_artist_search_key,
    mb_album_search_key,
    mb_artist_detail_key,
    mb_release_group_key,
    mb_release_key,
)
from infrastructure.resilience.retry import with_retry, CircuitBreaker

logger = logging.getLogger(__name__)

musicbrainzngs.set_useragent("Musicseerr", "1.0", "https://github.com/HabiRabbu/musicseerr")
musicbrainzngs.set_rate_limit(limit_or_interval=1.0)

_mb_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="musicbrainz"
)

_mb_semaphore = asyncio.Semaphore(10)


class MusicBrainzRepository:
    def __init__(self, cache: CacheInterface):
        self._cache = cache
    
    @staticmethod
    @with_retry(max_attempts=3, circuit_breaker=_mb_circuit_breaker)
    async def _mb_call(func, *args, **kwargs):
        """Execute MusicBrainz call with semaphore, retry, and circuit breaker."""
        async with _mb_semaphore:
            return await asyncio.to_thread(func, *args, **kwargs)
    
    @staticmethod
    def _should_include_release(
        release_group: dict[str, Any],
        included_secondary_types: Optional[set[str]] = None
    ) -> bool:
        secondary_types = set(map(str.lower, release_group.get("secondary-type-list", []) or []))
        
        if included_secondary_types is None:
            exclude_types = {"compilation", "live", "remix", "soundtrack", "dj-mix", "mixtape/street", "demo"}
            return secondary_types.isdisjoint(exclude_types)
        
        if not secondary_types:
            return "studio" in included_secondary_types
        
        return bool(secondary_types.intersection(included_secondary_types))
    
    @staticmethod
    def _extract_artist_name(release_group: dict[str, Any]) -> Optional[str]:
        artist_credit = release_group.get("artist-credit", [])
        if not isinstance(artist_credit, list) or not artist_credit:
            return None
        
        first_credit = artist_credit[0]
        if isinstance(first_credit, dict):
            return first_credit.get("name") or (first_credit.get("artist") or {}).get("name")
        return None
    
    @staticmethod
    def _parse_year(date_str: Optional[str]) -> Optional[int]:
        if not date_str:
            return None
        year = date_str.split("-", 1)[0]
        return int(year) if year.isdigit() else None
    
    @staticmethod
    def _get_score(item: dict[str, Any]) -> int:
        score = item.get("score") or item.get("ext:score")
        try:
            return int(score) if score else 0
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def _dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = {}
        for item in items:
            item_id = item.get("id")
            if item_id and item_id not in seen:
                seen[item_id] = item
        
        result = list(seen.values())
        result.sort(key=MusicBrainzRepository._get_score, reverse=True)
        return result
    
    def _map_artist_to_result(self, artist: dict[str, Any]) -> SearchResult:
        return SearchResult(
            type="artist",
            title=artist.get("name", "Unknown Artist"),
            musicbrainz_id=artist.get("id", ""),
            in_library=False,
        )
    
    def _map_release_group_to_result(
        self,
        rg: dict[str, Any],
        included_secondary_types: Optional[set[str]] = None
    ) -> Optional[SearchResult]:
        if not self._should_include_release(rg, included_secondary_types):
            return None
        
        return SearchResult(
            type="album",
            title=rg.get("title", "Unknown Album"),
            artist=self._extract_artist_name(rg),
            year=self._parse_year(rg.get("first-release-date")),
            musicbrainz_id=rg.get("id", ""),
            in_library=False,
        )
    
    async def search_artists(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0
    ) -> list[SearchResult]:
        cache_key = mb_artist_search_key(query, limit, offset)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            search_query = f'artist:"{query}"^3 OR artistaccent:"{query}"^3 OR alias:"{query}"^2 OR {query}'
            
            result = await self._mb_call(
                musicbrainzngs.search_artists,
                query=search_query,
                limit=min(100, max(limit * 2, 25)),
                offset=offset
            )
            artists = result.get("artist-list", [])
            artists = self._dedupe_by_id(artists)
            artists = artists[:limit]
            
            results = [self._map_artist_to_result(a) for a in artists]
            
            await self._cache.set(cache_key, results, ttl_seconds=1800)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz artist search failed: {e}")
            return []
    
    async def search_albums(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        included_secondary_types: Optional[set[str]] = None
    ) -> list[SearchResult]:
        cache_key = mb_album_search_key(query, limit, offset, included_secondary_types)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            internal_limit = min(100, max(int(limit * 1.5), 25))
            
            result = await self._mb_call(
                musicbrainzngs.search_release_groups,
                query=f'releasegroup:"{query}"^3 OR release:"{query}"^2 OR {query}',
                limit=internal_limit,
                offset=offset
            )
            release_groups = result.get("release-group-list", [])
            release_groups = self._dedupe_by_id(release_groups)
            
            results = []
            for rg in release_groups:
                mapped = self._map_release_group_to_result(rg, included_secondary_types)
                if mapped:
                    results.append(mapped)
                if len(results) >= limit:
                    break
            
            await self._cache.set(cache_key, results, ttl_seconds=1800)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz album search failed: {e}")
            return []
    
    async def search_grouped(
        self,
        query: str,
        limits: dict[str, int],
        buckets: Optional[list[str]] = None,
        included_secondary_types: Optional[set[str]] = None
    ) -> dict[str, list[SearchResult]]:
        results = {}
        
        if not buckets or "artists" in buckets:
            artists_limit = limits.get("artists", 10)
            results["artists"] = await self.search_artists(query, limit=artists_limit)
        
        if not buckets or "albums" in buckets:
            albums_limit = limits.get("albums", 10)
            results["albums"] = await self.search_albums(
                query,
                limit=albums_limit,
                included_secondary_types=included_secondary_types
            )
        
        return results
    
    async def get_artist_by_id(self, mbid: str) -> Optional[dict]:
        cache_key = mb_artist_detail_key(mbid)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = await self._mb_call(
                musicbrainzngs.get_artist_by_id,
                mbid,
                includes=["tags", "aliases", "url-rels"]
            )
            artist = result.get("artist")
            
            if not artist:
                return None
            
            limit = 50
            
            first_batch = await self._mb_call(
                musicbrainzngs.browse_release_groups,
                artist=mbid,
                limit=limit,
                offset=0
            )
            
            all_release_groups = []
            total_count = 0
            if first_batch and "release-group-list" in first_batch:
                all_release_groups.extend(first_batch["release-group-list"])
                total_count = int(first_batch.get("release-group-count", 0))
            
            if all_release_groups:
                artist["release-group-list"] = all_release_groups
            
            artist["release-group-count"] = total_count
            
            await self._cache.set(cache_key, artist, ttl_seconds=21600)
            return artist
        except Exception as e:
            logger.error(f"Failed to fetch artist {mbid}: {e}")
            return None
    
    async def get_artist_release_groups(
        self,
        artist_mbid: str,
        offset: int = 0,
        limit: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            result = await self._mb_call(
                musicbrainzngs.browse_release_groups,
                artist=artist_mbid,
                limit=limit,
                offset=offset
            )
            
            release_groups = []
            total_count = 0
            
            if result and "release-group-list" in result:
                release_groups = result["release-group-list"]
                total_count = int(result.get("release-group-count", 0))
            
            return release_groups, total_count
        except Exception as e:
            logger.error(f"Failed to fetch release groups for artist {artist_mbid} at offset {offset}: {e}")
            return [], 0
    
    async def get_release_group_by_id(
        self,
        mbid: str,
        includes: Optional[list[str]] = None
    ) -> Optional[dict]:
        """Get release group by ID with optional includes."""
        if includes is None:
            includes = ["artist-credits", "releases"]
        
        cache_key = mb_release_group_key(mbid, includes)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = await self._mb_call(
                musicbrainzngs.get_release_group_by_id,
                mbid,
                includes=includes
            )
            release_group = result.get("release-group")
            await self._cache.set(cache_key, release_group, ttl_seconds=3600)
            return release_group
        except Exception as e:
            logger.error(f"Failed to fetch release group {mbid}: {e}")
            return None
    
    async def get_release_by_id(
        self,
        release_id: str,
        includes: Optional[list[str]] = None
    ) -> Optional[dict]:
        """Get release details with recordings and labels."""
        if includes is None:
            includes = ["recordings", "labels"]
        
        cache_key = mb_release_key(release_id, includes)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = await self._mb_call(
                musicbrainzngs.get_release_by_id,
                release_id,
                includes=includes
            )
            release = result.get("release")
            await self._cache.set(cache_key, release, ttl_seconds=3600)
            return release
        except Exception as e:
            logger.error(f"Failed to fetch release {release_id}: {e}")
            return None

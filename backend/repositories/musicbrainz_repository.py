import asyncio
import logging
from typing import Any, Optional
import musicbrainzngs
from api.v1.schemas.search import SearchResult
from services.preferences_service import PreferencesService
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import (
    mb_artist_search_key,
    mb_album_search_key,
    mb_artist_detail_key,
    mb_release_group_key,
    mb_release_key,
)
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from infrastructure.resilience.rate_limiter import TokenBucketRateLimiter
from infrastructure.queue.priority_queue import RequestPriority, get_priority_queue
from infrastructure.http.deduplication import RequestDeduplicator

logger = logging.getLogger(__name__)

musicbrainzngs.set_useragent("Musicseerr", "1.0", "https://github.com/HabiRabbu/musicseerr")
musicbrainzngs.set_rate_limit(limit_or_interval=False)

_mb_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="musicbrainz"
)

_mb_rate_limiter = TokenBucketRateLimiter(rate=1.0, capacity=3)

_mb_deduplicator = RequestDeduplicator()


class MusicBrainzRepository:
    def __init__(self, cache: CacheInterface, preferences_service: PreferencesService):
        self._cache = cache
        self._preferences_service = preferences_service
    
    @staticmethod
    @with_retry(max_attempts=3, circuit_breaker=_mb_circuit_breaker)
    async def _mb_call(func, *args, priority: RequestPriority = RequestPriority.USER_INITIATED, **kwargs):
        priority_mgr = get_priority_queue()
        semaphore = await priority_mgr.acquire_slot(priority)
        async with semaphore:
            await _mb_rate_limiter.acquire()
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
                offset=offset,
                priority=RequestPriority.USER_INITIATED
            )
            artists = result.get("artist-list", [])
            artists = self._dedupe_by_id(artists)
            artists = artists[:limit]
            
            results = [self._map_artist_to_result(a) for a in artists]
            
            advanced_settings = self._preferences_service.get_advanced_settings()
            await self._cache.set(cache_key, results, ttl_seconds=advanced_settings.cache_ttl_search)
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
                offset=offset,
                priority=RequestPriority.USER_INITIATED
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
            
            advanced_settings = self._preferences_service.get_advanced_settings()
            await self._cache.set(cache_key, results, ttl_seconds=advanced_settings.cache_ttl_search)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz album search failed: {e}")
            return []
    
    async def search_artists_by_tag(
        self,
        tag: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[SearchResult]:
        cache_key = f"mb_artists_by_tag:{tag.lower()}:{limit}:{offset}"
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = await self._mb_call(
                musicbrainzngs.search_artists,
                tag=tag.lower(),
                limit=min(100, limit),
                offset=offset,
                priority=RequestPriority.BACKGROUND_SYNC
            )
            artists = result.get("artist-list", [])
            artists = self._dedupe_by_id(artists)
            
            results = [self._map_artist_to_result(a) for a in artists[:limit]]
            
            advanced_settings = self._preferences_service.get_advanced_settings()
            await self._cache.set(cache_key, results, ttl_seconds=advanced_settings.cache_ttl_search * 2)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz artist tag search failed for '{tag}': {e}")
            return []
    
    async def search_release_groups_by_tag(
        self,
        tag: str,
        limit: int = 50,
        offset: int = 0,
        included_secondary_types: Optional[set[str]] = None
    ) -> list[SearchResult]:
        cache_key = f"mb_rg_by_tag:{tag.lower()}:{limit}:{offset}"
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            internal_limit = min(100, max(int(limit * 1.5), 25))
            
            result = await self._mb_call(
                musicbrainzngs.search_release_groups,
                tag=tag.lower(),
                limit=internal_limit,
                offset=offset,
                priority=RequestPriority.BACKGROUND_SYNC
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
            
            advanced_settings = self._preferences_service.get_advanced_settings()
            await self._cache.set(cache_key, results, ttl_seconds=advanced_settings.cache_ttl_search * 2)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz release group tag search failed for '{tag}': {e}")
            return []
    
    async def search_grouped(
        self,
        query: str,
        limits: dict[str, int],
        buckets: Optional[list[str]] = None,
        included_secondary_types: Optional[set[str]] = None
    ) -> dict[str, list[SearchResult]]:
        advanced_settings = self._preferences_service.get_advanced_settings()
        _mb_rate_limiter.update_capacity(advanced_settings.musicbrainz_concurrent_searches)
        
        tasks = []
        task_keys = []
        
        if not buckets or "artists" in buckets:
            tasks.append(self.search_artists(query, limit=limits.get("artists", 10)))
            task_keys.append("artists")
        
        if not buckets or "albums" in buckets:
            tasks.append(self.search_albums(
                query,
                limit=limits.get("albums", 10),
                included_secondary_types=included_secondary_types
            ))
            task_keys.append("albums")
        
        if not tasks:
            return {}
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        for key, result in zip(task_keys, results_list):
            if isinstance(result, Exception):
                logger.error(f"Search {key} failed: {result}")
                results[key] = []
            else:
                results[key] = result
        
        return results
    
    async def get_artist_by_id(self, mbid: str) -> Optional[dict]:
        cache_key = mb_artist_detail_key(mbid)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        dedupe_key = f"mb:artist:{mbid}"
        return await _mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_artist_by_id(mbid, cache_key))
    
    async def _fetch_artist_by_id(self, mbid: str, cache_key: str) -> Optional[dict]:
        try:
            result = await self._mb_call(
                musicbrainzngs.get_artist_by_id,
                mbid,
                includes=["tags", "aliases", "url-rels"],
                priority=RequestPriority.USER_INITIATED
            )
            artist = result.get("artist")
            
            if not artist:
                return None
            
            limit = 50
            
            first_batch = await self._mb_call(
                musicbrainzngs.browse_release_groups,
                artist=mbid,
                limit=limit,
                offset=0,
                priority=RequestPriority.USER_INITIATED
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
                offset=offset,
                priority=RequestPriority.BACKGROUND_SYNC
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
        if includes is None:
            includes = ["artist-credits", "releases"]
        
        cache_key = mb_release_group_key(mbid, includes)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        includes_str = ",".join(sorted(includes))
        dedupe_key = f"mb:rg:{mbid}:{includes_str}"
        return await _mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_release_group_by_id(mbid, includes, cache_key))
    
    async def _fetch_release_group_by_id(
        self,
        mbid: str,
        includes: list[str],
        cache_key: str
    ) -> Optional[dict]:
        try:
            result = await self._mb_call(
                musicbrainzngs.get_release_group_by_id,
                mbid,
                includes=includes,
                priority=RequestPriority.USER_INITIATED
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
        if includes is None:
            includes = ["recordings", "labels"]
        
        cache_key = mb_release_key(release_id, includes)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        includes_str = ",".join(sorted(includes))
        dedupe_key = f"mb:release:{release_id}:{includes_str}"
        return await _mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_release_by_id(release_id, includes, cache_key))
    
    async def _fetch_release_by_id(
        self,
        release_id: str,
        includes: list[str],
        cache_key: str
    ) -> Optional[dict]:
        try:
            result = await self._mb_call(
                musicbrainzngs.get_release_by_id,
                release_id,
                includes=includes,
                priority=RequestPriority.USER_INITIATED
            )
            release = result.get("release")
            await self._cache.set(cache_key, release, ttl_seconds=3600)
            return release
        except Exception as e:
            logger.error(f"Failed to fetch release {release_id}: {e}")
            return None

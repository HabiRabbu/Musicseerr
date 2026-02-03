import logging
from typing import Any, Optional
import musicbrainzngs
from api.v1.schemas.search import SearchResult
from services.preferences_service import PreferencesService
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import mb_artist_search_key, mb_artist_detail_key
from infrastructure.queue.priority_queue import RequestPriority
from repositories.musicbrainz_base import (
    mb_call,
    mb_deduplicator,
    dedupe_by_id,
)

logger = logging.getLogger(__name__)


class MusicBrainzArtistMixin:
    _cache: CacheInterface
    _preferences_service: PreferencesService

    def _map_artist_to_result(self, artist: dict[str, Any]) -> SearchResult:
        return SearchResult(
            type="artist",
            title=artist.get("name", "Unknown Artist"),
            musicbrainz_id=artist.get("id", ""),
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

            result = await mb_call(
                musicbrainzngs.search_artists,
                query=search_query,
                limit=min(100, max(limit * 2, 25)),
                offset=offset,
                priority=RequestPriority.USER_INITIATED
            )
            artists = result.get("artist-list", [])
            artists = dedupe_by_id(artists)
            artists = artists[:limit]

            results = [self._map_artist_to_result(a) for a in artists]

            advanced_settings = self._preferences_service.get_advanced_settings()
            await self._cache.set(cache_key, results, ttl_seconds=advanced_settings.cache_ttl_search)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz artist search failed: {e}")
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
            result = await mb_call(
                musicbrainzngs.search_artists,
                tag=tag.lower(),
                limit=min(100, limit),
                offset=offset,
                priority=RequestPriority.BACKGROUND_SYNC
            )
            artists = result.get("artist-list", [])
            artists = dedupe_by_id(artists)

            results = [self._map_artist_to_result(a) for a in artists[:limit]]

            advanced_settings = self._preferences_service.get_advanced_settings()
            await self._cache.set(cache_key, results, ttl_seconds=advanced_settings.cache_ttl_search * 2)
            return results
        except Exception as e:
            logger.error(f"MusicBrainz artist tag search failed for '{tag}': {e}")
            return []

    async def get_artist_by_id(self, mbid: str) -> Optional[dict]:
        cache_key = mb_artist_detail_key(mbid)

        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        dedupe_key = f"mb:artist:{mbid}"
        return await mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_artist_by_id(mbid, cache_key))

    async def _fetch_artist_by_id(self, mbid: str, cache_key: str) -> Optional[dict]:
        try:
            result = await mb_call(
                musicbrainzngs.get_artist_by_id,
                mbid,
                includes=["tags", "aliases", "url-rels"],
                priority=RequestPriority.USER_INITIATED
            )
            artist = result.get("artist")

            if not artist:
                return None

            limit = 50

            first_batch = await mb_call(
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
            result = await mb_call(
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

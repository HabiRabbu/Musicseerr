import asyncio
import logging
from typing import Any, Optional

from api.v1.schemas.search import SearchResult
from services.preferences_service import PreferencesService
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import mb_artist_search_key, mb_artist_detail_key
from infrastructure.queue.priority_queue import RequestPriority
from repositories.musicbrainz_base import (
    mb_api_get,
    mb_deduplicator,
    dedupe_by_id,
    get_score,
)

logger = logging.getLogger(__name__)


FILTERED_ARTIST_MBIDS = {
    "89ad4ac3-39f7-470e-963a-56509c546377",  # Various Artists
    "41ece0f7-91f6-4c87-982c-3a39c5a02586",  # /v/
    "125ec42a-7229-4250-afc5-e057484327fe",  # [Unknown]
}

FILTERED_ARTIST_NAMES = {
    "various artists",
    "[unknown]",
    "/v/",
}


class MusicBrainzArtistMixin:
    _cache: CacheInterface
    _preferences_service: PreferencesService

    def _map_artist_to_result(self, artist: dict[str, Any]) -> Optional[SearchResult]:
        artist_id = artist.get("id", "")
        if artist_id in FILTERED_ARTIST_MBIDS:
            return None
        
        name = artist.get("name", "Unknown Artist")
        if name.lower() in FILTERED_ARTIST_NAMES:
            return None
        
        return SearchResult(
            type="artist",
            title=name,
            musicbrainz_id=artist_id,
            in_library=False,
            disambiguation=artist.get("disambiguation") or None,
            type_info=artist.get("type") or None,
            score=get_score(artist),
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

            result = await mb_api_get(
                "/artist",
                params={
                    "query": search_query,
                    "limit": min(100, max(limit * 2, 25)),
                    "offset": offset,
                },
                priority=RequestPriority.USER_INITIATED,
            )
            artists = result.get("artists", [])
            artists = dedupe_by_id(artists)

            results = []
            for a in artists:
                mapped = self._map_artist_to_result(a)
                if mapped:
                    results.append(mapped)
                if len(results) >= limit:
                    break

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
            result = await mb_api_get(
                "/artist",
                params={
                    "query": f"tag:{tag.lower()}",
                    "limit": min(100, limit),
                    "offset": offset,
                },
                priority=RequestPriority.BACKGROUND_SYNC,
            )
            artists = result.get("artists", [])
            artists = dedupe_by_id(artists)

            results = [r for a in artists[:limit] if (r := self._map_artist_to_result(a)) is not None]

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

    async def get_artist_relations(self, mbid: str) -> Optional[dict]:
        detail_key = mb_artist_detail_key(mbid)
        cached = await self._cache.get(detail_key)
        if cached is not None:
            return cached

        rels_key = f"mb:artist_rels:{mbid}"
        cached_rels = await self._cache.get(rels_key)
        if cached_rels is not None:
            return cached_rels

        dedupe_key = f"mb:artist_rels:{mbid}"
        return await mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_artist_relations(mbid, rels_key))

    async def _fetch_artist_relations(self, mbid: str, cache_key: str) -> Optional[dict]:
        try:
            result = await mb_api_get(
                f"/artist/{mbid}",
                params={"inc": "url-rels"},
                priority=RequestPriority.IMAGE_FETCH,
            )
            if not result:
                return None
            await self._cache.set(cache_key, result, ttl_seconds=86400)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch artist relations {mbid}: {e}")
            return None

    async def _fetch_artist_by_id(self, mbid: str, cache_key: str) -> Optional[dict]:
        try:
            limit = 50

            artist_result, browse_result = await asyncio.gather(
                mb_api_get(
                    f"/artist/{mbid}",
                    params={"inc": "tags+aliases+url-rels"},
                    priority=RequestPriority.USER_INITIATED,
                ),
                mb_api_get(
                    "/release-group",
                    params={"artist": mbid, "limit": limit, "offset": 0},
                    priority=RequestPriority.USER_INITIATED,
                ),
            )

            if not artist_result:
                return None

            all_release_groups = browse_result.get("release-groups", [])
            total_count = int(browse_result.get("release-group-count", 0))

            if all_release_groups:
                artist_result["release-group-list"] = all_release_groups

            artist_result["release-group-count"] = total_count

            await self._cache.set(cache_key, artist_result, ttl_seconds=21600)

            asyncio.create_task(self._warm_release_group_cache(all_release_groups[:6]))

            return artist_result
        except Exception as e:
            logger.error(f"Failed to fetch artist {mbid}: {e}")
            return None

    async def _warm_release_group_cache(self, release_groups: list[dict[str, Any]]) -> None:
        for rg in release_groups:
            rg_id = rg.get("id")
            if not rg_id:
                continue
            try:
                await self.get_release_group_by_id(rg_id)
            except Exception:
                pass

    async def get_artist_release_groups(
        self,
        artist_mbid: str,
        offset: int = 0,
        limit: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            result = await mb_api_get(
                "/release-group",
                params={"artist": artist_mbid, "limit": limit, "offset": offset},
                priority=RequestPriority.BACKGROUND_SYNC,
            )

            release_groups = result.get("release-groups", [])
            total_count = int(result.get("release-group-count", 0))

            return release_groups, total_count
        except Exception as e:
            logger.error(f"Failed to fetch release groups for artist {artist_mbid} at offset {offset}: {e}")
            return [], 0

    async def get_release_groups_by_artist(
        self,
        artist_mbid: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        release_groups, _ = await self.get_artist_release_groups(artist_mbid, offset=0, limit=limit)
        return release_groups

import logging
from typing import Any, Optional

from api.v1.schemas.search import SearchResult
from services.preferences_service import PreferencesService
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import mb_album_search_key, mb_release_group_key, mb_release_key
from infrastructure.queue.priority_queue import RequestPriority
from repositories.musicbrainz_base import (
    mb_api_get,
    mb_deduplicator,
    dedupe_by_id,
    get_score,
    should_include_release,
    extract_artist_name,
    parse_year,
    build_musicbrainz_tag_query,
)

logger = logging.getLogger(__name__)


def _rg_priority(rg: dict) -> int:
    rg_type = rg.get("primary-type", "")
    priority = 0
    if rg_type == "Album":
        priority = 3
    elif rg_type == "EP":
        priority = 2
    elif rg_type == "Single":
        priority = 1
    secondary = rg.get("secondary-types", [])
    if secondary:
        priority = max(0, priority - 1)
    return priority


def _pick_best_release_group(releases: list[dict]) -> tuple[str, str] | None:
    candidates: list[tuple[str, str, int]] = []
    for release in releases:
        rg = release.get("release-group", {})
        rg_id = rg.get("id")
        rg_title = rg.get("title", "")
        if rg_id:
            candidates.append((rg_id, rg_title, _rg_priority(rg)))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[2], reverse=True)
    return (candidates[0][0], candidates[0][1])


class MusicBrainzAlbumMixin:
    _cache: CacheInterface
    _preferences_service: PreferencesService

    def _map_release_group_to_result(
        self,
        rg: dict[str, Any],
        included_secondary_types: Optional[set[str]] = None
    ) -> Optional[SearchResult]:
        if not should_include_release(rg, included_secondary_types):
            return None

        primary_type = rg.get("primary-type", "")
        secondary_types = rg.get("secondary-types", [])
        if secondary_types:
            type_info = f"{primary_type} + {', '.join(secondary_types)}"
        else:
            type_info = primary_type or None

        return SearchResult(
            type="album",
            title=rg.get("title", "Unknown Album"),
            artist=extract_artist_name(rg),
            year=parse_year(rg.get("first-release-date")),
            musicbrainz_id=rg.get("id", ""),
            in_library=False,
            type_info=type_info,
            disambiguation=rg.get("disambiguation") or None,
            score=get_score(rg),
        )

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

            result = await mb_api_get(
                "/release-group",
                params={
                    "query": f'releasegroup:"{query}"^3 OR release:"{query}"^2 OR {query}',
                    "limit": internal_limit,
                    "offset": offset,
                },
                priority=RequestPriority.USER_INITIATED,
            )
            release_groups = result.get("release-groups", [])
            release_groups = dedupe_by_id(release_groups)

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

            result = await mb_api_get(
                "/release-group",
                params={
                    "query": build_musicbrainz_tag_query(tag),
                    "limit": internal_limit,
                    "offset": offset,
                },
                priority=RequestPriority.BACKGROUND_SYNC,
            )
            release_groups = result.get("release-groups", [])
            release_groups = dedupe_by_id(release_groups)

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

        includes_str = "+".join(sorted(includes))
        dedupe_key = f"mb:rg:{mbid}:{includes_str}"
        return await mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_release_group_by_id(mbid, includes, cache_key))

    async def _fetch_release_group_by_id(
        self,
        mbid: str,
        includes: list[str],
        cache_key: str
    ) -> Optional[dict]:
        try:
            inc_str = "+".join(sorted(includes))
            result = await mb_api_get(
                f"/release-group/{mbid}",
                params={"inc": inc_str},
                priority=RequestPriority.USER_INITIATED,
            )
            if not result:
                return None
            await self._cache.set(cache_key, result, ttl_seconds=3600)
            return result
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

        includes_str = "+".join(sorted(includes))
        dedupe_key = f"mb:release:{release_id}:{includes_str}"
        return await mb_deduplicator.dedupe(dedupe_key, lambda: self._fetch_release_by_id(release_id, includes, cache_key))

    async def _fetch_release_by_id(
        self,
        release_id: str,
        includes: list[str],
        cache_key: str
    ) -> Optional[dict]:
        try:
            inc_str = "+".join(sorted(includes))
            result = await mb_api_get(
                f"/release/{release_id}",
                params={"inc": inc_str},
                priority=RequestPriority.USER_INITIATED,
            )
            if not result:
                return None
            await self._cache.set(cache_key, result, ttl_seconds=3600)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch release {release_id}: {e}")
            return None

    async def get_release_group_id_from_release(
        self,
        release_id: str
    ) -> Optional[str]:
        cache_key = f"mb:release_to_rg:{release_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.info(f"[MB] Cache hit for release {release_id[:8]}: '{cached[:8] if cached else 'empty'}'")
            return cached if cached != "" else None

        dedupe_key = f"mb:release_to_rg:{release_id}"
        return await mb_deduplicator.dedupe(
            dedupe_key,
            lambda: self._fetch_release_group_id_from_release(release_id, cache_key),
        )

    async def _fetch_release_group_id_from_release(
        self,
        release_id: str,
        cache_key: str,
    ) -> Optional[str]:
        try:
            logger.info(f"[MB] Fetching release group for release {release_id[:8]}")
            result = await mb_api_get(
                f"/release/{release_id}",
                params={"inc": "release-groups"},
                priority=RequestPriority.BACKGROUND_SYNC,
            )
            rg = result.get("release-group", {})
            rg_id = rg.get("id")
            logger.info(f"[MB] Resolved release {release_id[:8]} -> release_group {rg_id}")
            await self._cache.set(cache_key, rg_id or "", ttl_seconds=86400)
            return rg_id
        except Exception as e:
            logger.warning(f"[MB] Failed to get release group for release {release_id[:8]}: {e}")
            await self._cache.set(cache_key, "", ttl_seconds=3600)
            return None

    @staticmethod
    def extract_youtube_url_from_relations(entity_data: dict) -> str | None:
        for rel in entity_data.get("relations", []):
            url_obj = rel.get("url", {})
            url = url_obj.get("resource", "") if isinstance(url_obj, dict) else ""
            if "youtube.com" in url or "youtu.be" in url:
                return url
        return None

    @staticmethod
    def youtube_url_to_embed(url: str) -> str | None:
        import re
        patterns = [
            r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"youtu\.be/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return f"https://www.youtube.com/embed/{match.group(1)}"
        return None

    async def get_recording_by_id(
        self,
        recording_id: str,
        includes: list[str] | None = None,
    ) -> dict | None:
        if includes is None:
            includes = ["url-rels"]
        inc_str = "+".join(sorted(includes))
        cache_key = f"mb:recording:{recording_id}:{inc_str}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            result = await mb_api_get(
                f"/recording/{recording_id}",
                params={"inc": inc_str},
                priority=RequestPriority.BACKGROUND_SYNC,
            )
            if not result:
                return None
            await self._cache.set(cache_key, result, ttl_seconds=3600)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch recording {recording_id}: {e}")
            return None

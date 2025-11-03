"""MusicBrainz API integration for searching artists and albums."""
import asyncio
import logging
from typing import Any, Optional

import musicbrainzngs

from models import SearchResult
from utils.cache import cached

logger = logging.getLogger(__name__)

# Configure MusicBrainz client
musicbrainzngs.set_useragent("Musicseerr", "1.0", "https://github.com/HabiRabbu/musicseerr")
musicbrainzngs.set_rate_limit(limit_or_interval=1.0)

# Excluded secondary release types (compilations, live, etc.)
_EXCLUDE_SECONDARY_TYPES = {"compilation", "live", "remix", "soundtrack", "dj-mix", "mixtape/street", "demo"}


def _extract_artist_name(release_group: dict[str, Any]) -> Optional[str]:
    """Extract artist name from release group artist credits."""
    artist_credit = release_group.get("artist-credit", [])
    if not isinstance(artist_credit, list) or not artist_credit:
        return None
    
    first_credit = artist_credit[0]
    if isinstance(first_credit, dict):
        return first_credit.get("name") or (first_credit.get("artist") or {}).get("name")
    return None


def _parse_year(date_str: Optional[str]) -> Optional[int]:
    """Extract year from ISO date string."""
    if not date_str:
        return None
    year = date_str.split("-", 1)[0]
    return int(year) if year.isdigit() else None


def _get_score(item: dict[str, Any]) -> int:
    """Extract MusicBrainz search score."""
    score = item.get("score") or item.get("ext:score")
    try:
        return int(score) if score else 0
    except (ValueError, TypeError):
        return 0


def _dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate items by ID and sort by score."""
    seen = {}
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen:
            seen[item_id] = item
    
    result = list(seen.values())
    result.sort(key=_get_score, reverse=True)
    return result


def _is_studio_album(release_group: dict[str, Any]) -> bool:
    """Check if release group is a studio album (not live, compilation, etc.)."""
    secondary_types = set(map(str.lower, release_group.get("secondary-type-list", []) or []))
    return secondary_types.isdisjoint(_EXCLUDE_SECONDARY_TYPES)


def _map_artist_to_result(artist: dict[str, Any]) -> SearchResult:
    """Convert MusicBrainz artist to SearchResult."""
    return SearchResult(
        type="artist",
        title=artist.get("name", "Unknown Artist"),
        musicbrainz_id=artist.get("id", ""),
        in_library=False,
    )


def _map_album_to_result(release_group: dict[str, Any]) -> SearchResult:
    """Convert MusicBrainz release group to SearchResult."""
    return SearchResult(
        type="album",
        title=release_group.get("title", "Unknown Album"),
        artist=_extract_artist_name(release_group),
        year=_parse_year(release_group.get("first-release-date")),
        musicbrainz_id=release_group.get("id", ""),
        in_library=False,
    )


def _search_artists_sync(query: str, limit: int, offset: int = 0) -> list[dict[str, Any]]:
    """Synchronous artist search."""
    # Build optimized query string
    search_query = f'artist:"{query}"^3 OR artistaccent:"{query}"^3 OR alias:"{query}"^2 OR {query}'
    
    results = musicbrainzngs.search_artists(
        query=search_query,
        limit=min(100, max(limit * 2, 25)),
        offset=offset
    )
    
    artists = results.get("artist-list", [])
    artists.sort(key=_get_score, reverse=True)
    return artists[:limit]


def _search_release_groups_sync(
    query: str,
    limit: int,
    offset: int = 0,
    primary_type: str = "album",
    studio_only: bool = False,
    detailed: bool = False,
) -> list[dict[str, Any]]:
    """Synchronous release group search."""
    internal_limit = min(100, max(int(limit * 1.5), 25))
    
    # Simple search
    results_1 = musicbrainzngs.search_release_groups(
        releasegroup=query,
        primarytype=primary_type,
        strict=False,
        limit=internal_limit,
        offset=offset,
    ).get("release-group-list", [])
    
    # Detailed search if requested
    if detailed:
        results_2 = musicbrainzngs.search_release_groups(
            query=f'releasegroup:"{query}"^3 OR artistname:"{query}"^2 OR artist:"{query}"^2',
            primarytype=primary_type,
            limit=internal_limit,
            offset=offset,
        ).get("release-group-list", [])
        
        release_groups = _dedupe_by_id(results_1 + results_2)
    else:
        release_groups = _dedupe_by_id(results_1)
    
    # Filter studio albums if requested
    if studio_only:
        release_groups = [rg for rg in release_groups if _is_studio_album(rg)]
    
    return release_groups[:limit]


@cached(ttl_seconds=300, key_prefix="mb_artists:")
async def _search_artists_cached(query: str, limit: int, offset: int) -> list[dict[str, Any]]:
    """Cached async wrapper for artist search."""
    return await asyncio.to_thread(_search_artists_sync, query, limit, offset)


@cached(ttl_seconds=300, key_prefix="mb_albums:")
async def _search_albums_cached(
    query: str, limit: int, offset: int, studio_only: bool
) -> list[dict[str, Any]]:
    """Cached async wrapper for album search."""
    return await asyncio.to_thread(
        _search_release_groups_sync,
        query,
        limit,
        offset,
        "album",
        studio_only,
        False,
    )


async def search_musicbrainz_grouped(
    query: str,
    limits: Optional[dict[str, int]] = None,
    buckets: Optional[list[str]] = None,
) -> dict[str, list[SearchResult]]:
    """Search MusicBrainz for artists and albums with parallel queries.
    
    Args:
        query: Search query string
        limits: Dict with "artists" and "albums" limits
        buckets: List of search types to include (["artists", "albums"])
    
    Returns:
        Dict with "artists" and "albums" lists of SearchResult objects
    """
    buckets = buckets or ["artists", "albums"]
    limits = limits or {}
    
    tasks = []
    task_keys = []
    
    # Build parallel search tasks
    if "artists" in buckets:
        artist_limit = limits.get("artists", 10)
        tasks.append(_search_artists_cached(query, artist_limit, 0))
        task_keys.append("artists")
    
    if "albums" in buckets:
        album_limit = limits.get("albums", 10)
        tasks.append(_search_albums_cached(query, album_limit, 0, True))
        task_keys.append("albums")
    
    # Execute searches in parallel
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle errors gracefully
    processed = []
    for result in raw_results:
        processed.append([] if isinstance(result, Exception) else result)
    
    raw_data = dict(zip(task_keys, processed))
    
    # Map to SearchResult objects
    return {
        "artists": [_map_artist_to_result(a) for a in raw_data.get("artists", [])],
        "albums": [_map_album_to_result(rg) for rg in raw_data.get("albums", [])],
    }


async def search_musicbrainz_bucket(
    query: str,
    bucket: str,
    limit: int = 50,
    offset: int = 0,
) -> list[SearchResult]:
    """Search a single MusicBrainz bucket (artists or albums).
    
    Args:
        query: Search query string
        bucket: Type of search ("artists" or "albums")
        limit: Max results to return
        offset: Pagination offset
    
    Returns:
        List of SearchResult objects
    """
    bucket = bucket.lower()
    
    async def fetch():
        if bucket == "artists":
            return await asyncio.to_thread(_search_artists_sync, query, limit, offset)
        elif bucket == "albums":
            return await asyncio.to_thread(
                _search_release_groups_sync,
                query,
                limit,
                offset,
                "album",
                True,  # studio_only
                True,  # detailed
            )
        return []
    
    try:
        raw_data = await fetch()
    except Exception as e:
        logger.error(f"MusicBrainz search error for {bucket}: {e}")
        return []
    
    # Map to SearchResult objects
    if bucket == "artists":
        return [_map_artist_to_result(a) for a in raw_data]
    return [_map_album_to_result(rg) for rg in raw_data]


@cached(ttl_seconds=1800, key_prefix="mb_artist_detail:")
async def get_artist_by_id(artist_id: str) -> Optional[dict[str, Any]]:
    """Get detailed artist information by MusicBrainz ID.
    
    Args:
        artist_id: MusicBrainz artist ID
    
    Returns:
        Artist data dict or None if not found
    """
    def fetch():
        try:
            result = musicbrainzngs.get_artist_by_id(
                artist_id,
                includes=["release-groups", "tags", "aliases", "url-rels", "ratings"],
            )
            return result.get("artist")
        except Exception as e:
            logger.error(f"Failed to fetch artist {artist_id}: {e}")
            return None
    
    return await asyncio.to_thread(fetch)
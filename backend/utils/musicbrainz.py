import asyncio
from typing import Any, Dict, List, Optional, Iterable

import musicbrainzngs
from models import SearchResult

musicbrainzngs.set_useragent("Musicseerr", "1.0", "https://github.com/HabiRabbu/musicseerr")
musicbrainzngs.set_rate_limit(limit_or_interval=1.0)


def _extract_artist_name_from_rg(rg: Dict[str, Any]) -> Optional[str]:
    ac = rg.get("artist-credit") or []
    if isinstance(ac, list) and ac:
        first = ac[0]
        if isinstance(first, dict):
            return first.get("name") or (first.get("artist") or {}).get("name")
    return None


def _parse_year(first_release_date: Optional[str]) -> Optional[int]:
    if not first_release_date:
        return None
    y = first_release_date.split("-", 1)[0]
    return int(y) if y.isdigit() else None


def _mb_score(item: Dict[str, Any]) -> int:
    s = item.get("score") or item.get("ext:score")
    try:
        return int(s)
    except Exception:
        return 0


def _dedupe_and_sort(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for it in items:
        iid = it.get("id")
        if iid and iid not in by_id:
            by_id[iid] = it
    out = list(by_id.values())
    out.sort(key=_mb_score, reverse=True)
    return out


def _map_artist_to_search_result(artist: Dict[str, Any]) -> SearchResult:
    return SearchResult(
        type="artist",
        title=artist.get("name"),
        artist=None,
        year=None,
        musicbrainz_id=artist.get("id"),
        in_library=False,
    )


def _map_album_to_search_result(rg: Dict[str, Any]) -> SearchResult:
    return SearchResult(
        type="album",
        title=rg.get("title"),
        artist=_extract_artist_name_from_rg(rg),
        year=_parse_year(rg.get("first-release-date")),
        musicbrainz_id=rg.get("id"),
        in_library=False,
    )


def _search_artists_blocking(q: str, limit: int, offset: int = 0) -> List[Dict[str, Any]]:
    query = f'artist:"{q}"^3 OR artistaccent:"{q}"^3 OR alias:"{q}"^2 OR {q}'
    results = musicbrainzngs.search_artists(
        query=query, 
        limit=min(100, max(limit * 2, 25)),
        offset=offset
    ).get("artist-list", [])
    
    results.sort(key=_mb_score, reverse=True)
    return results[:limit]


_EXCLUDE_SECS = {"compilation", "live", "remix", "soundtrack", "dj-mix", "mixtape/street", "demo"}


def _is_studio_rg(rg: Dict[str, Any]) -> bool:
    secs = set(map(str.lower, rg.get("secondary-type-list", []) or []))
    return secs.isdisjoint(_EXCLUDE_SECS)


def _search_rgs_blocking(
    q: str,
    limit: int,
    offset: int = 0,
    primary: str = "album",
    secondary: Optional[str] = None,
    studio_only: bool = False,
    fast: bool = True,
) -> List[Dict[str, Any]]:
    internal_limit = min(100, max(int(limit * 1.5), 25))

    q1 = musicbrainzngs.search_release_groups(
        releasegroup=q,
        primarytype=primary,
        **({"secondarytype": secondary} if secondary else {}),
        strict=False,
        limit=internal_limit,
        offset=offset,
    ).get("release-group-list", [])

    if fast:
        rgs = _dedupe_and_sort(q1)
    else:
        q2 = musicbrainzngs.search_release_groups(
            query=f'releasegroup:"{q}"^3 OR artistname:"{q}"^2 OR artist:"{q}"^2',
            primarytype=primary,
            **({"secondarytype": secondary} if secondary else {}),
            limit=internal_limit,
            offset=offset,
        ).get("release-group-list", [])
        rgs = _dedupe_and_sort(q1 + q2)

    if studio_only:
        rgs = [rg for rg in rgs if _is_studio_rg(rg)]

    return rgs[:limit]


async def search_musicbrainz_grouped(
    q: str,
    limits: dict[str, int] | None = None,
    buckets: Optional[List[str]] = None,
) -> Dict[str, List[SearchResult]]:
    if not buckets:
        buckets = ["artists", "albums"]
    
    if not limits:
        limits = {}

    tasks = []
    result_keys = []
    
    if "artists" in buckets:
        artist_limit = limits.get("artists", 10)
        tasks.append(asyncio.to_thread(_search_artists_blocking, q, artist_limit, 0))
        result_keys.append("artists")
    
    if "albums" in buckets:
        album_limit = limits.get("albums", 10)
        tasks.append(asyncio.to_thread(
            _search_rgs_blocking, 
            q, 
            album_limit, 
            0,              # offset
            "album",        # primary
            None,           # secondary
            True,           # studio_only
            True            # fast - use single query for speed
        ))
        result_keys.append("albums")
    
    raw_results = await asyncio.gather(*tasks)
    
    raw = dict(zip(result_keys, raw_results))

    grouped: Dict[str, List[SearchResult]] = {
        "artists": [_map_artist_to_search_result(a) for a in raw.get("artists", [])],
        "albums": [_map_album_to_search_result(rg) for rg in raw.get("albums", [])],
    }

    return grouped


async def search_musicbrainz_bucket(
    q: str,
    bucket: str,
    limit: int = 50,
    offset: int = 0,
) -> List[SearchResult]:
    bucket = bucket.lower()

    def sync_one() -> List[Dict[str, Any]]:
        if bucket == "artists":
            return _search_artists_blocking(q, limit, offset)
        if bucket == "albums":
            return _search_rgs_blocking(q, limit, offset, primary="album", studio_only=True, fast=False)
        return []

    raw = await asyncio.to_thread(sync_one)

    out: List[SearchResult] = []
    if bucket == "artists":
        out = [_map_artist_to_search_result(a) for a in raw]
    else:
        out = [_map_album_to_search_result(rg) for rg in raw]
    
    return out


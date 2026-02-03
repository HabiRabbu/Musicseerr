import asyncio
import logging
from typing import Any, Optional
import musicbrainzngs
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from infrastructure.resilience.rate_limiter import TokenBucketRateLimiter
from infrastructure.queue.priority_queue import RequestPriority, get_priority_queue
from infrastructure.http.deduplication import RequestDeduplicator
from core.config import get_settings

logger = logging.getLogger(__name__)

_mb_initialized = False


def _init_musicbrainz():
    global _mb_initialized
    if not _mb_initialized:
        settings = get_settings()
        musicbrainzngs.set_useragent(
            "Musicseerr",
            "1.0",
            f"{settings.contact_email}; https://www.musicseerr.com"
        )
        musicbrainzngs.set_rate_limit(limit_or_interval=False)
        _mb_initialized = True

mb_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="musicbrainz"
)

mb_rate_limiter = TokenBucketRateLimiter(rate=1.0, capacity=5)

mb_deduplicator = RequestDeduplicator()


@with_retry(max_attempts=3, circuit_breaker=mb_circuit_breaker)
async def mb_call(func, *args, priority: RequestPriority = RequestPriority.USER_INITIATED, **kwargs):
    _init_musicbrainz()
    priority_mgr = get_priority_queue()
    semaphore = await priority_mgr.acquire_slot(priority)
    async with semaphore:
        await mb_rate_limiter.acquire()
        return await asyncio.to_thread(func, *args, **kwargs)


def should_include_release(
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


def extract_artist_name(release_group: dict[str, Any]) -> Optional[str]:
    artist_credit = release_group.get("artist-credit", [])
    if not isinstance(artist_credit, list) or not artist_credit:
        return None

    first_credit = artist_credit[0]
    if isinstance(first_credit, dict):
        return first_credit.get("name") or (first_credit.get("artist") or {}).get("name")
    return None


def parse_year(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    year = date_str.split("-", 1)[0]
    return int(year) if year.isdigit() else None


def get_score(item: dict[str, Any]) -> int:
    score = item.get("score") or item.get("ext:score")
    try:
        return int(score) if score else 0
    except (ValueError, TypeError):
        return 0


def dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {}
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen:
            seen[item_id] = item

    result = list(seen.values())
    result.sort(key=get_score, reverse=True)
    return result

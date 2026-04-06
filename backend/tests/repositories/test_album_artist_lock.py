"""Tests for MUS-14 album.py changes: per-artist lock, safe LRU eviction."""

import asyncio

import pytest

from repositories.lidarr.album import _get_artist_lock, _artist_locks, _MAX_ARTIST_LOCKS


@pytest.fixture(autouse=True)
def _clear_locks():
    """Reset the module-level lock dict between tests."""
    _artist_locks.clear()
    yield
    _artist_locks.clear()


def test_get_artist_lock_returns_same_lock_for_same_mbid():
    lock1 = _get_artist_lock("artist-aaa")
    lock2 = _get_artist_lock("artist-aaa")
    assert lock1 is lock2


def test_get_artist_lock_returns_different_locks_for_different_mbids():
    lock1 = _get_artist_lock("artist-aaa")
    lock2 = _get_artist_lock("artist-bbb")
    assert lock1 is not lock2


def test_lru_eviction_respects_max():
    for i in range(_MAX_ARTIST_LOCKS + 10):
        _get_artist_lock(f"artist-{i}")
    assert len(_artist_locks) <= _MAX_ARTIST_LOCKS


@pytest.mark.asyncio
async def test_lru_eviction_skips_held_locks():
    """A lock that is currently held must not be evicted."""
    first_lock = _get_artist_lock("artist-held")
    await first_lock.acquire()

    try:
        for i in range(_MAX_ARTIST_LOCKS + 5):
            _get_artist_lock(f"artist-fill-{i}")

        assert "artist-held" in _artist_locks
        assert _artist_locks["artist-held"] is first_lock
    finally:
        first_lock.release()


@pytest.mark.asyncio
async def test_per_artist_lock_serializes_concurrent_calls():
    """Concurrent calls for the same artist should be serialized."""
    call_order: list[str] = []

    async def simulated_add(artist_mbid: str, label: str):
        lock = _get_artist_lock(artist_mbid)
        async with lock:
            call_order.append(f"{label}-start")
            await asyncio.sleep(0.1)
            call_order.append(f"{label}-end")

    await asyncio.gather(
        simulated_add("same-artist", "A"),
        simulated_add("same-artist", "B"),
    )

    # One must complete fully before the other starts
    a_start = call_order.index("A-start")
    a_end = call_order.index("A-end")
    b_start = call_order.index("B-start")
    b_end = call_order.index("B-end")

    serialized = (a_end < b_start) or (b_end < a_start)
    assert serialized, f"Expected serialized execution, got: {call_order}"


@pytest.mark.asyncio
async def test_different_artists_run_concurrently():
    """Requests for different artists should NOT be serialized."""
    active = {"count": 0, "max": 0}
    lock = asyncio.Lock()

    async def simulated_add(artist_mbid: str):
        artist_lock = _get_artist_lock(artist_mbid)
        async with artist_lock:
            async with lock:
                active["count"] += 1
                active["max"] = max(active["max"], active["count"])
            await asyncio.sleep(0.1)
            async with lock:
                active["count"] -= 1

    await asyncio.gather(
        simulated_add("artist-X"),
        simulated_add("artist-Y"),
        simulated_add("artist-Z"),
    )

    assert active["max"] >= 2, f"Expected concurrent execution, max active was {active['max']}"

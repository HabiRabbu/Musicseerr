"""Tests for discovery precache double-execution prevention and throttling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.artist_discovery_service import ArtistDiscoveryService
import services.artist_discovery_service as _ads_module


@pytest.fixture(autouse=True)
def _reset_precache_flag():
    _ads_module._discovery_precache_running = False
    yield
    _ads_module._discovery_precache_running = False


def _make_service(*, lb_configured: bool = True, lastfm_enabled: bool = False):
    lb_repo = MagicMock()
    lb_repo.is_configured.return_value = lb_configured

    lastfm_repo = MagicMock() if lastfm_enabled else None
    prefs = MagicMock()
    prefs.is_lastfm_enabled.return_value = lastfm_enabled
    advanced = MagicMock()
    advanced.artist_discovery_precache_concurrency = 2
    prefs.get_advanced_settings.return_value = advanced

    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    library_db = AsyncMock()
    library_db.get_all_artist_mbids = AsyncMock(return_value=set())

    svc = ArtistDiscoveryService(
        listenbrainz_repo=lb_repo,
        musicbrainz_repo=MagicMock(),
        library_db=library_db,
        lidarr_repo=MagicMock(),
        memory_cache=cache,
        lastfm_repo=lastfm_repo,
        preferences_service=prefs,
    )
    return svc


@pytest.mark.asyncio
async def test_duplicate_invocation_skipped():
    """Second call returns 0 immediately when precache is already running."""
    svc = _make_service()

    gate = asyncio.Event()

    async def slow_similar(*args, **kwargs):
        await gate.wait()
        return MagicMock()

    with (
        patch.object(svc, "get_similar_artists", new_callable=AsyncMock, side_effect=slow_similar),
        patch.object(svc, "get_top_songs", new_callable=AsyncMock, return_value=MagicMock()),
        patch.object(svc, "get_top_albums", new_callable=AsyncMock, return_value=MagicMock()),
    ):
        task1 = asyncio.create_task(
            svc.precache_artist_discovery(["mbid-a"], delay=0)
        )
        await asyncio.sleep(0.01)

        assert _ads_module._discovery_precache_running is True
        result2 = await svc.precache_artist_discovery(["mbid-b"], delay=0)
        assert result2 == 0

        gate.set()
        result1 = await task1
        assert result1 >= 0

    assert _ads_module._discovery_precache_running is False


@pytest.mark.asyncio
async def test_lock_released_after_exception():
    """Flag is cleared even when precache raises an unexpected error."""
    svc = _make_service()

    with patch.object(
        svc, "_do_precache_artist_discovery",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await svc.precache_artist_discovery(["mbid-a"], delay=0)

    assert _ads_module._discovery_precache_running is False

    with (
        patch.object(svc, "get_similar_artists", new_callable=AsyncMock, return_value=MagicMock()),
        patch.object(svc, "get_top_songs", new_callable=AsyncMock, return_value=MagicMock()),
        patch.object(svc, "get_top_albums", new_callable=AsyncMock, return_value=MagicMock()),
    ):
        result = await svc.precache_artist_discovery(["mbid-a"], delay=0)
        assert result >= 0


@pytest.mark.asyncio
async def test_delay_holds_semaphore_slot():
    """Delay is applied inside the semaphore, blocking other artists from starting."""
    svc = _make_service()
    timestamps: list[float] = []

    loop = asyncio.get_event_loop()

    async def track_similar(*args, **kwargs):
        timestamps.append(loop.time())
        return MagicMock()

    with (
        patch.object(svc, "get_similar_artists", new_callable=AsyncMock, side_effect=track_similar),
        patch.object(svc, "get_top_songs", new_callable=AsyncMock, return_value=MagicMock()),
        patch.object(svc, "get_top_albums", new_callable=AsyncMock, return_value=MagicMock()),
    ):
        await svc.precache_artist_discovery(
            ["mbid-a", "mbid-b", "mbid-c", "mbid-d"],
            delay=0.15,
        )

    assert len(timestamps) == 4
    # With concurrency=2 and delay=0.15s inside semaphore, the 3rd artist
    # cannot start until one of the first two finishes its delay.
    # The gap between the 2nd and 3rd timestamps should be >= delay.
    sorted_ts = sorted(timestamps)
    gap = sorted_ts[2] - sorted_ts[0]
    assert gap >= 0.1, f"Expected >=0.1s gap due to semaphore-held delay, got {gap:.3f}s"


@pytest.mark.asyncio
async def test_cached_artists_skip_api_calls():
    """Artists with all cache keys populated skip API fetches entirely."""
    svc = _make_service()

    call_count = 0

    async def counting_similar(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return MagicMock()

    svc._cache.get = AsyncMock(return_value=MagicMock())

    with (
        patch.object(svc, "get_similar_artists", new_callable=AsyncMock, side_effect=counting_similar),
        patch.object(svc, "get_top_songs", new_callable=AsyncMock, return_value=MagicMock()),
        patch.object(svc, "get_top_albums", new_callable=AsyncMock, return_value=MagicMock()),
    ):
        result = await svc.precache_artist_discovery(
            ["mbid-a", "mbid-b"],
            delay=0,
        )

    assert call_count == 0, "Expected no API calls when all cache keys are populated"
    assert result == 2


@pytest.mark.asyncio
async def test_guard_survives_instance_recreation():
    """Module-level flag prevents overlap even when a new service instance is created."""
    svc1 = _make_service()
    svc2 = _make_service()

    gate = asyncio.Event()

    async def slow_similar(*args, **kwargs):
        await gate.wait()
        return MagicMock()

    with (
        patch.object(svc1, "get_similar_artists", new_callable=AsyncMock, side_effect=slow_similar),
        patch.object(svc1, "get_top_songs", new_callable=AsyncMock, return_value=MagicMock()),
        patch.object(svc1, "get_top_albums", new_callable=AsyncMock, return_value=MagicMock()),
    ):
        task1 = asyncio.create_task(
            svc1.precache_artist_discovery(["mbid-a"], delay=0)
        )
        await asyncio.sleep(0.01)

        result2 = await svc2.precache_artist_discovery(["mbid-b"], delay=0)
        assert result2 == 0, "Second instance should be blocked by module-level flag"

        gate.set()
        await task1

    assert _ads_module._discovery_precache_running is False

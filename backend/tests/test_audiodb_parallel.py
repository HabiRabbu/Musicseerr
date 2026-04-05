"""Tests for AudioDB parallel prewarm with semaphore gating."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.precache.audiodb_phase import AudioDBPhase


def _make_settings(concurrency=4, delay=0.0, enabled=True):
    s = MagicMock()
    s.audiodb_enabled = enabled
    s.audiodb_name_search_fallback = False
    s.audiodb_prewarm_concurrency = concurrency
    s.audiodb_prewarm_delay = delay
    return s


def _make_prefs(settings=None):
    if settings is None:
        settings = _make_settings()
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = settings
    return prefs


def _make_status_service():
    status = MagicMock()
    status.update_phase = AsyncMock()
    status.update_progress = AsyncMock()
    status.persist_progress = AsyncMock()
    status.skip_phase = AsyncMock()
    status.is_cancelled.return_value = False
    return status


def _make_cover_repo(tmpdir):
    repo = AsyncMock()
    repo.cache_dir = Path(tmpdir)
    return repo


class TestAudioDBParallel:
    @pytest.mark.asyncio
    async def test_concurrent_processing(self):
        """Multiple artists should be processed concurrently up to the semaphore limit."""
        concurrency = 2
        prefs = _make_prefs(_make_settings(concurrency=concurrency, delay=0.0))

        audiodb_svc = AsyncMock()
        audiodb_svc.get_cached_artist_images = AsyncMock(return_value=None)
        audiodb_svc.get_cached_album_images = AsyncMock(return_value=None)
        audiodb_svc.fetch_and_cache_artist_images = AsyncMock(return_value=None)

        with tempfile.TemporaryDirectory() as tmpdir:
            phase = AudioDBPhase(
                cover_repo=_make_cover_repo(tmpdir),
                preferences_service=prefs,
                audiodb_image_service=audiodb_svc,
            )

            artists = [{"mbid": f"mbid-{i:04d}", "name": f"Artist {i}"} for i in range(6)]
            status = _make_status_service()

            await phase.precache_audiodb_data(artists, [], status)

            assert audiodb_svc.fetch_and_cache_artist_images.call_count == 6
            assert status.update_progress.call_count == 6
            assert True

    @pytest.mark.asyncio
    async def test_concurrency_respects_setting(self):
        """The concurrency semaphore should limit parallel execution."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        prefs = _make_prefs(_make_settings(concurrency=2, delay=0.0))
        audiodb_svc = AsyncMock()
        audiodb_svc.get_cached_artist_images = AsyncMock(return_value=None)
        audiodb_svc.get_cached_album_images = AsyncMock(return_value=None)

        async def track_concurrency(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return None

        audiodb_svc.fetch_and_cache_artist_images = AsyncMock(side_effect=track_concurrency)

        with tempfile.TemporaryDirectory() as tmpdir:
            phase = AudioDBPhase(
                cover_repo=_make_cover_repo(tmpdir),
                preferences_service=prefs,
                audiodb_image_service=audiodb_svc,
            )

            artists = [{"mbid": f"mbid-{i:04d}", "name": f"Artist {i}"} for i in range(10)]
            status = _make_status_service()

            await phase.precache_audiodb_data(artists, [], status)

            assert max_concurrent <= 2
            assert max_concurrent >= 1
            assert True

    @pytest.mark.asyncio
    async def test_disabled_audiodb_skips(self):
        """When audiodb_enabled is False, phase should be skipped."""
        prefs = _make_prefs(_make_settings(enabled=False))

        phase = AudioDBPhase(
            cover_repo=AsyncMock(),
            preferences_service=prefs,
            audiodb_image_service=AsyncMock(),
        )

        status = _make_status_service()
        await phase.precache_audiodb_data([], [], status)

        status.skip_phase.assert_called_once_with('audiodb_prewarm')
        assert True

    @pytest.mark.asyncio
    async def test_all_cached_skips(self):
        """When all items are cached, phase should be skipped."""
        prefs = _make_prefs(_make_settings())

        audiodb_svc = AsyncMock()
        audiodb_svc.get_cached_artist_images = AsyncMock(return_value={"some": "data"})
        audiodb_svc.get_cached_album_images = AsyncMock(return_value={"some": "data"})

        phase = AudioDBPhase(
            cover_repo=AsyncMock(),
            preferences_service=prefs,
            audiodb_image_service=audiodb_svc,
        )

        artists = [{"mbid": "mbid-0001", "name": "Artist 1"}]
        status = _make_status_service()

        await phase.precache_audiodb_data(artists, [], status)

        status.skip_phase.assert_called_once_with('audiodb_prewarm')
        assert True

"""Tests for sync resume-on-failure behaviour."""

import asyncio
import sqlite3
import tempfile
import os
import threading

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.persistence.sync_state_store import SyncStateStore
from services.cache_status_service import CacheStatusService


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset CacheStatusService singleton between tests."""
    CacheStatusService._instance = None
    yield
    CacheStatusService._instance = None


class TestResumeOnFailure:
    @pytest.mark.asyncio
    async def test_complete_sync_preserves_state_on_failure(self):
        """On failure, sync state should be saved but NOT cleared."""
        store = AsyncMock()
        store.save_sync_state = AsyncMock()
        store.clear_sync_state = AsyncMock()
        store.clear_processed_items = AsyncMock()

        svc = CacheStatusService(store)
        await svc.start_sync('artists', 100)
        await svc.update_progress(50, "some artist")
        await svc.complete_sync("Sync stalled: no progress")

        store.save_sync_state.assert_called()
        last_call = store.save_sync_state.call_args
        assert last_call.kwargs.get('status') == 'failed'

        store.clear_sync_state.assert_not_called()
        store.clear_processed_items.assert_not_called()
        assert True

    @pytest.mark.asyncio
    async def test_complete_sync_clears_state_on_success(self):
        """On success, both sync_state and processed_items should be cleared."""
        store = AsyncMock()
        store.save_sync_state = AsyncMock()
        store.clear_sync_state = AsyncMock()
        store.clear_processed_items = AsyncMock()

        svc = CacheStatusService(store)
        await svc.start_sync('artists', 10)
        await svc.update_progress(10, "done")
        await svc.complete_sync(None)

        store.clear_sync_state.assert_called_once()
        store.clear_processed_items.assert_called_once()
        assert True

    @pytest.mark.asyncio
    async def test_last_progress_at_updates_on_progress(self):
        """get_last_progress_at should reflect the latest update_progress call."""
        store = AsyncMock()
        store.save_sync_state = AsyncMock()

        svc = CacheStatusService(store)
        await svc.start_sync('artists', 10)

        t1 = svc.get_last_progress_at()
        await asyncio.sleep(0.05)
        await svc.update_progress(5, "artist5")
        t2 = svc.get_last_progress_at()

        assert t2 > t1
        assert True

    @pytest.mark.asyncio
    async def test_last_progress_at_updates_on_phase_change(self):
        """get_last_progress_at should refresh when phase changes."""
        store = AsyncMock()
        store.save_sync_state = AsyncMock()

        svc = CacheStatusService(store)
        await svc.start_sync('artists', 10)

        t1 = svc.get_last_progress_at()
        await asyncio.sleep(0.05)
        await svc.update_phase('albums', 50)
        t2 = svc.get_last_progress_at()

        assert t2 > t1
        assert True


class TestSyncStateStoreClear:
    @pytest.mark.asyncio
    async def test_clear_processed_items_deletes_all(self):
        """clear_processed_items should execute a DELETE on processed_items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            write_lock = threading.Lock()
            store = SyncStateStore(db_path, write_lock)

            await store.mark_items_processed_batch("artist", ["mbid1", "mbid2"])
            items = await store.get_processed_items("artist")
            assert len(items) == 2

            await store.clear_processed_items()
            items = await store.get_processed_items("artist")
            assert len(items) == 0
            assert True

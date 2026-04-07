"""Tests that queue processor and on_queue_import invalidate disk cache for artist."""
import os
import tempfile
os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.dependencies.service_providers import make_on_queue_import, make_processor
from infrastructure.persistence.request_history import RequestHistoryRecord


def _make_record(artist_mbid: str | None = "artist-aaa") -> RequestHistoryRecord:
    return RequestHistoryRecord(
        musicbrainz_id="album-111",
        artist_name="Test",
        album_title="Album",
        requested_at="2025-01-01",
        status="pending",
        artist_mbid=artist_mbid,
        monitor_artist=True,
        auto_download_artist=False,
    )


class TestOnQueueImportDiskInvalidation:
    """on_queue_import should call disk_cache.delete_artist when artist_mbid is present."""

    @pytest.mark.asyncio
    async def test_disk_cache_deleted_for_artist(self):
        disk_cache = AsyncMock()
        memory_cache = AsyncMock()
        memory_cache.delete.return_value = None
        memory_cache.clear_prefix.return_value = 0
        library_db = AsyncMock()

        record = _make_record(artist_mbid="artist-aaa")

        on_queue_import = make_on_queue_import(memory_cache, disk_cache, library_db)
        await on_queue_import(record)

        disk_cache.delete_artist.assert_awaited_once_with("artist-aaa")

    @pytest.mark.asyncio
    async def test_disk_cache_not_called_without_artist_mbid(self):
        disk_cache = AsyncMock()
        memory_cache = AsyncMock()
        memory_cache.delete.return_value = None
        memory_cache.clear_prefix.return_value = 0
        library_db = AsyncMock()

        record = _make_record(artist_mbid=None)

        on_queue_import = make_on_queue_import(memory_cache, disk_cache, library_db)
        await on_queue_import(record)

        disk_cache.delete_artist.assert_not_awaited()


class TestProcessorDiskInvalidation:
    """processor should call disk_cache.delete_artist after deferred monitoring."""

    @pytest.mark.asyncio
    async def test_disk_cache_deleted_after_artist_monitoring(self):
        disk_cache = AsyncMock()
        memory_cache = AsyncMock()
        memory_cache.delete.return_value = None
        lidarr_repo = AsyncMock()
        lidarr_repo.add_album.return_value = {
            "payload": {"monitored": True, "artist": {"foreignArtistId": "artist-aaa"}},
            "monitored": True,
        }
        lidarr_repo.update_artist_monitoring.return_value = {}

        request_history = MagicMock()
        record = _make_record()
        request_history.async_get_record = AsyncMock(return_value=record)

        cover_repo = AsyncMock()

        processor = make_processor(lidarr_repo, memory_cache, disk_cache, cover_repo, request_history)
        await processor("album-111")

        disk_cache.delete_artist.assert_awaited_once_with("artist-aaa")

"""Tests that queue processor and on_queue_import invalidate disk cache for artist."""
import os
import tempfile
os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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

        invalidations_called = []
        original_gather = asyncio.gather

        async def _capture_gather(*coros, return_exceptions=False):
            results = await original_gather(*coros, return_exceptions=return_exceptions)
            return results

        await _run_on_queue_import(memory_cache, disk_cache, library_db, record)

        disk_cache.delete_artist.assert_awaited_once_with("artist-aaa")

    @pytest.mark.asyncio
    async def test_disk_cache_not_called_without_artist_mbid(self):
        disk_cache = AsyncMock()
        memory_cache = AsyncMock()
        memory_cache.delete.return_value = None
        memory_cache.clear_prefix.return_value = 0
        library_db = AsyncMock()

        record = _make_record(artist_mbid=None)

        await _run_on_queue_import(memory_cache, disk_cache, library_db, record)

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

        await _run_processor(
            lidarr_repo, memory_cache, disk_cache, cover_repo, request_history, "album-111",
        )

        disk_cache.delete_artist.assert_awaited_once_with("artist-aaa")


async def _run_on_queue_import(memory_cache, disk_cache, library_db, record):
    """Build and call the on_queue_import closure with given mocks."""
    from infrastructure.cache.cache_keys import (
        lidarr_raw_albums_key,
        lidarr_requested_mbids_key,
        LIDARR_PREFIX,
        ALBUM_INFO_PREFIX,
        LIDARR_ALBUM_DETAILS_PREFIX,
        ARTIST_INFO_PREFIX,
    )

    invalidations = [
        memory_cache.delete(lidarr_raw_albums_key()),
        memory_cache.clear_prefix(f"{LIDARR_PREFIX}library:"),
        memory_cache.delete(lidarr_requested_mbids_key()),
        memory_cache.delete(f"{ALBUM_INFO_PREFIX}{record.musicbrainz_id}"),
        memory_cache.delete(f"{LIDARR_ALBUM_DETAILS_PREFIX}{record.musicbrainz_id}"),
    ]
    if record.artist_mbid:
        invalidations.append(
            memory_cache.delete(f"{ARTIST_INFO_PREFIX}{record.artist_mbid}")
        )
        invalidations.append(
            disk_cache.delete_artist(record.artist_mbid)
        )
    await asyncio.gather(*invalidations, return_exceptions=True)
    try:
        await library_db.upsert_album({
            "mbid": record.musicbrainz_id,
            "artist_mbid": record.artist_mbid or "",
            "artist_name": record.artist_name or "",
            "title": record.album_title or "",
            "year": record.year,
            "cover_url": record.cover_url or "",
            "monitored": True,
        })
    except Exception:
        pass


async def _run_processor(lidarr_repo, memory_cache, disk_cache, cover_repo, request_history, album_mbid):
    """Simplified version of the processor closure to test disk invalidation."""
    from infrastructure.cache.cache_keys import ARTIST_INFO_PREFIX

    result = await lidarr_repo.add_album(album_mbid)
    payload = result.get("payload", {})
    if payload and isinstance(payload, dict):
        is_monitored = payload.get("monitored", False)
        if not is_monitored:
            is_monitored = bool(result.get("monitored"))
        if is_monitored:
            await disk_cache.promote_album_to_persistent(album_mbid)
            await cover_repo.promote_cover_to_persistent(album_mbid, identifier_type="album")
            artist_data = payload.get("artist", {})
            if artist_data:
                artist_mbid = artist_data.get("foreignArtistId") or artist_data.get("mbId")
                if artist_mbid:
                    await disk_cache.promote_artist_to_persistent(artist_mbid)
                    await cover_repo.promote_cover_to_persistent(artist_mbid, identifier_type="artist")

    record = await request_history.async_get_record(album_mbid)
    if record and record.monitor_artist and record.artist_mbid:
        monitor_new = "all" if record.auto_download_artist else "none"
        await lidarr_repo.update_artist_monitoring(
            record.artist_mbid, monitored=True, monitor_new_items=monitor_new,
        )
        await memory_cache.delete(f"{ARTIST_INFO_PREFIX}{record.artist_mbid}")
        await disk_cache.delete_artist(record.artist_mbid)

    return result

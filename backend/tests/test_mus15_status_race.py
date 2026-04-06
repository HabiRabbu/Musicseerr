"""Tests for MUS-15: album status race condition fixes."""

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import pytest


# ---------- Fix 1: library_service.get_library_mbids merges library_db ----------

@pytest.mark.asyncio
async def test_get_library_mbids_merges_library_db():
    """Library mbids should union Lidarr API results with library_db MBIDs."""
    from services.library_service import LibraryService

    lidarr_repo = MagicMock()
    lidarr_repo.is_configured.return_value = True
    lidarr_repo.get_library_mbids = AsyncMock(return_value={"aaa", "bbb"})

    library_db = MagicMock()
    library_db.get_all_album_mbids = AsyncMock(return_value={"CCC", "DDD"})

    svc = LibraryService(
        lidarr_repo=lidarr_repo,
        library_db=library_db,
        cover_repo=MagicMock(),
        preferences_service=MagicMock(),
    )
    result = await svc.get_library_mbids()
    result_set = {m.lower() for m in result}

    assert result_set == {"aaa", "bbb", "ccc", "ddd"}, "Should contain both Lidarr and library_db MBIDs"
    assert len(result) == 4


@pytest.mark.asyncio
async def test_get_library_mbids_handles_library_db_overlap():
    """Overlapping MBIDs should be deduplicated."""
    from services.library_service import LibraryService

    lidarr_repo = MagicMock()
    lidarr_repo.is_configured.return_value = True
    lidarr_repo.get_library_mbids = AsyncMock(return_value={"aaa", "bbb"})

    library_db = MagicMock()
    library_db.get_all_album_mbids = AsyncMock(return_value={"AAA", "bbb"})

    svc = LibraryService(
        lidarr_repo=lidarr_repo,
        library_db=library_db,
        cover_repo=MagicMock(),
        preferences_service=MagicMock(),
    )
    result = await svc.get_library_mbids()

    assert len(result) == 2, "Overlapping MBIDs should be deduplicated (case-insensitive)"


@pytest.mark.asyncio
async def test_get_library_mbids_recently_imported_visible():
    """Album upserted to library_db (by on_import) appears even when Lidarr cache is stale."""
    from services.library_service import LibraryService

    # Lidarr API returns old cached data — doesn't include the newly imported album
    lidarr_repo = MagicMock()
    lidarr_repo.is_configured.return_value = True
    lidarr_repo.get_library_mbids = AsyncMock(return_value={"old-album"})

    # library_db has the newly imported album (upserted by on_import callback)
    library_db = MagicMock()
    library_db.get_all_album_mbids = AsyncMock(return_value={"old-album", "newly-imported"})

    svc = LibraryService(
        lidarr_repo=lidarr_repo,
        library_db=library_db,
        cover_repo=MagicMock(),
        preferences_service=MagicMock(),
    )
    result = await svc.get_library_mbids()
    result_set = set(result)

    assert "newly-imported" in result_set, "Recently imported album must appear in library mbids"


@pytest.mark.asyncio
async def test_get_library_mbids_degrades_when_library_db_fails():
    """If library_db fails, endpoint should degrade to Lidarr-only MBIDs."""
    from services.library_service import LibraryService

    lidarr_repo = MagicMock()
    lidarr_repo.is_configured.return_value = True
    lidarr_repo.get_library_mbids = AsyncMock(return_value={"aaa", "bbb"})

    library_db = MagicMock()
    library_db.get_all_album_mbids = AsyncMock(side_effect=RuntimeError("DB locked"))

    svc = LibraryService(
        lidarr_repo=lidarr_repo,
        library_db=library_db,
        cover_repo=MagicMock(),
        preferences_service=MagicMock(),
    )
    result = await svc.get_library_mbids()
    result_set = set(result)

    assert result_set == {"aaa", "bbb"}, "Should fall back to Lidarr-only when library_db fails"


# ---------- Fix 2: queue worker fires import callback ----------

@pytest.mark.asyncio
async def test_queue_worker_fires_import_callback_when_has_files():
    """When the queue worker detects has_files, the import callback should fire."""
    from infrastructure.queue.request_queue import RequestQueue
    from infrastructure.persistence.request_history import RequestHistoryRecord

    callback_called = asyncio.Event()
    callback_record = {}

    async def on_import(record):
        callback_record["mbid"] = record.musicbrainz_id
        callback_record["artist_mbid"] = record.artist_mbid
        callback_called.set()

    history = MagicMock()
    # First call: cancel check (returns original pending record)
    # Second call: enriched record for callback (after field updates)
    original_record = RequestHistoryRecord(
        musicbrainz_id="test-mbid",
        artist_name="Test Artist",
        album_title="Test Album",
        requested_at="2026-01-01T00:00:00Z",
        status="pending",
    )
    enriched_record = RequestHistoryRecord(
        musicbrainz_id="test-mbid",
        artist_name="Test Artist",
        album_title="Test Album",
        requested_at="2026-01-01T00:00:00Z",
        status="imported",
        artist_mbid="artist-mbid",
    )
    history.async_get_record = AsyncMock(side_effect=[original_record, enriched_record])
    history.async_update_status = AsyncMock()
    history.async_update_lidarr_album_id = AsyncMock()
    history.async_update_cover_url = AsyncMock()
    history.async_update_artist_mbid = AsyncMock()

    q = RequestQueue(
        processor=AsyncMock(),
        request_history=history,
        on_import_callback=on_import,
    )

    result = {
        "payload": {
            "id": 42,
            "statistics": {"trackFileCount": 5},
            "artist": {"foreignArtistId": "artist-mbid"},
        }
    }
    await q._update_history_on_result("test-mbid", result)

    assert callback_called.is_set(), "Import callback should have been called"
    assert callback_record["mbid"] == "test-mbid"
    assert callback_record["artist_mbid"] == "artist-mbid", "Callback should receive enriched record"


@pytest.mark.asyncio
async def test_queue_worker_no_callback_when_downloading():
    """When the queue worker detects no files, import callback should NOT fire."""
    from infrastructure.queue.request_queue import RequestQueue
    from infrastructure.persistence.request_history import RequestHistoryRecord

    callback_called = asyncio.Event()

    async def on_import(record):
        callback_called.set()

    history = MagicMock()
    original_record = RequestHistoryRecord(
        musicbrainz_id="test-mbid",
        artist_name="Test Artist",
        album_title="Test Album",
        requested_at="2026-01-01T00:00:00Z",
        status="pending",
    )
    history.async_get_record = AsyncMock(return_value=original_record)
    history.async_update_status = AsyncMock()
    history.async_update_lidarr_album_id = AsyncMock()
    history.async_update_cover_url = AsyncMock()
    history.async_update_artist_mbid = AsyncMock()

    q = RequestQueue(
        processor=AsyncMock(),
        request_history=history,
        on_import_callback=on_import,
    )

    result = {
        "payload": {
            "id": 42,
            "statistics": {"trackFileCount": 0},
            "artist": {"foreignArtistId": "artist-mbid"},
        }
    }
    await q._update_history_on_result("test-mbid", result)

    assert not callback_called.is_set(), "Import callback should NOT fire when trackFileCount=0"

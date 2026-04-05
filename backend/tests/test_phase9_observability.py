"""Phase 9 observability contract tests.

Verifies that every key log event fires with the required fields, and that
SSE / cache-stats wiring propagates AudioDB data end-to-end.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import msgspec
import pytest

from tests.helpers import assert_log_fields
from repositories.audiodb_models import (
    AudioDBArtistImages,
    AudioDBArtistResponse,
    AudioDBAlbumImages,
    AudioDBAlbumResponse,
)
from services.audiodb_image_service import AudioDBImageService

TEST_MBID = "cc197bad-dc9c-440d-a5b5-d52ba2e14234"
TEST_ALBUM_MBID = "1dc4c347-a1db-32aa-b14f-bc9cc507b843"

SAMPLE_ARTIST_RESP = AudioDBArtistResponse(
    idArtist="111239",
    strArtist="Coldplay",
    strMusicBrainzID=TEST_MBID,
    strArtistThumb="https://example.com/thumb.jpg",
    strArtistFanart="https://example.com/fanart.jpg",
)

SAMPLE_ALBUM_RESP = AudioDBAlbumResponse(
    idAlbum="2115888",
    strAlbum="Parachutes",
    strMusicBrainzID=TEST_ALBUM_MBID,
    strAlbumThumb="https://example.com/album_thumb.jpg",
    strAlbumBack="https://example.com/album_back.jpg",
)


def _make_settings(enabled=True, name_search_fallback=False):
    s = MagicMock()
    s.audiodb_enabled = enabled
    s.audiodb_name_search_fallback = name_search_fallback
    s.cache_ttl_audiodb_found = 604800
    s.cache_ttl_audiodb_not_found = 86400
    s.cache_ttl_audiodb_library = 1209600
    s.audiodb_prewarm_concurrency = 4
    s.audiodb_prewarm_delay = 0.0
    return s


def _make_image_service(settings=None, disk_cache=None, repo=None):
    if settings is None:
        settings = _make_settings()
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = settings
    if disk_cache is None:
        disk_cache = AsyncMock()
        disk_cache.get_audiodb_artist = AsyncMock(return_value=None)
        disk_cache.get_audiodb_album = AsyncMock(return_value=None)
        disk_cache.set_audiodb_artist = AsyncMock()
        disk_cache.set_audiodb_album = AsyncMock()
    if repo is None:
        repo = AsyncMock()
    return AudioDBImageService(
        audiodb_repo=repo,
        disk_cache=disk_cache,
        preferences_service=prefs,
    )




CACHE_REQUIRED_FIELDS = ["action", "entity_type", "mbid", "lookup_source"]


class TestCacheLogContract:
    @pytest.mark.asyncio
    async def test_miss_includes_lookup_source(self, caplog):
        svc = _make_image_service()
        with caplog.at_level("DEBUG"):
            await svc.get_cached_artist_images(TEST_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS)
        assert any("action=miss" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_corrupt_includes_lookup_source(self, caplog):
        disk = AsyncMock()
        disk.get_audiodb_artist = AsyncMock(return_value="not-a-dict")
        disk.delete_entity = AsyncMock()
        svc = _make_image_service(disk_cache=disk)
        with caplog.at_level("DEBUG"):
            await svc.get_cached_artist_images(TEST_MBID)

        msgs = assert_log_fields(
            caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS,
        )
        assert any("action=corrupt" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_hit_includes_lookup_source(self, caplog):
        images = AudioDBArtistImages(
            thumb_url="https://example.com/thumb.jpg",
            is_negative=False,
            lookup_source="mbid",
        )
        raw = msgspec.structs.asdict(images)
        disk = AsyncMock()
        disk.get_audiodb_artist = AsyncMock(return_value=raw)
        svc = _make_image_service(disk_cache=disk)
        with caplog.at_level("DEBUG"):
            await svc.get_cached_artist_images(TEST_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS)
        assert any("action=hit" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_write_mbid_includes_lookup_source(self, caplog):
        repo = AsyncMock()
        repo.get_artist_by_mbid = AsyncMock(return_value=SAMPLE_ARTIST_RESP)
        svc = _make_image_service(repo=repo)
        with caplog.at_level("DEBUG"):
            await svc.fetch_and_cache_artist_images(TEST_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS)
        assert any("action=write" in m and "lookup_source=mbid" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_fetch_error_mbid_includes_lookup_source(self, caplog):
        repo = AsyncMock()
        repo.get_artist_by_mbid = AsyncMock(side_effect=Exception("network"))
        svc = _make_image_service(repo=repo)
        with caplog.at_level("DEBUG"):
            await svc.fetch_and_cache_artist_images(TEST_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS)
        assert any("action=fetch_error" in m and "lookup_source=mbid" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_album_miss_includes_lookup_source(self, caplog):
        svc = _make_image_service()
        with caplog.at_level("DEBUG"):
            await svc.get_cached_album_images(TEST_ALBUM_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS)
        assert any("action=miss" in m and "entity_type=album" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_album_write_mbid_includes_lookup_source(self, caplog):
        repo = AsyncMock()
        repo.get_album_by_mbid = AsyncMock(return_value=SAMPLE_ALBUM_RESP)
        svc = _make_image_service(repo=repo)
        with caplog.at_level("DEBUG"):
            await svc.fetch_and_cache_album_images(TEST_ALBUM_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.cache", CACHE_REQUIRED_FIELDS)
        assert any("action=write" in m and "entity_type=album" in m for m in msgs)




LOOKUP_REQUIRED_FIELDS = ["entity", "lookup_type", "found", "elapsed_ms"]


class TestLookupLogContract:
    @pytest.fixture(autouse=True)
    def _reset_resilience(self):
        from repositories.audiodb_repository import _audiodb_circuit_breaker
        _audiodb_circuit_breaker.reset()
        yield
        _audiodb_circuit_breaker.reset()

    @pytest.fixture(autouse=True)
    def _stub_retry_sleep(self):
        with patch("infrastructure.resilience.retry.asyncio.sleep", new=AsyncMock()):
            yield

    def _make_repo(self):
        from repositories.audiodb_repository import AudioDBRepository
        client = AsyncMock(spec=httpx.AsyncClient)
        prefs = MagicMock()
        settings = MagicMock()
        settings.audiodb_enabled = True
        settings.audiodb_api_key = "test_key"
        prefs.get_advanced_settings.return_value = settings
        return AudioDBRepository(
            http_client=client,
            preferences_service=prefs,
            api_key="test_key",
        )

    def _mock_response(self, status_code=200, json_data=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.content = msgspec.json.encode(json_data or {})
        return resp

    @pytest.mark.asyncio
    async def test_artist_mbid_found_logs_lookup(self, caplog):
        repo = self._make_repo()
        data = {"artists": [{
            "idArtist": "111239", "strArtist": "Coldplay",
            "strMusicBrainzID": TEST_MBID,
            "strArtistThumb": "https://example.com/thumb.jpg",
        }]}
        repo._client.get = AsyncMock(return_value=self._mock_response(200, data))
        with caplog.at_level("DEBUG"):
            await repo.get_artist_by_mbid(TEST_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.lookup", LOOKUP_REQUIRED_FIELDS)
        assert any("found=true" in m and "entity=artist" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_artist_mbid_not_found_logs_lookup(self, caplog):
        repo = self._make_repo()
        repo._client.get = AsyncMock(return_value=self._mock_response(200, {"artists": None}))
        with caplog.at_level("DEBUG"):
            await repo.get_artist_by_mbid(TEST_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.lookup", LOOKUP_REQUIRED_FIELDS)
        assert any("found=false" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_album_mbid_found_logs_lookup(self, caplog):
        repo = self._make_repo()
        data = {"album": [{
            "idAlbum": "2115888", "strAlbum": "Parachutes",
            "strMusicBrainzID": TEST_ALBUM_MBID,
            "strAlbumThumb": "https://example.com/thumb.jpg",
        }]}
        repo._client.get = AsyncMock(return_value=self._mock_response(200, data))
        with caplog.at_level("DEBUG"):
            await repo.get_album_by_mbid(TEST_ALBUM_MBID)

        msgs = assert_log_fields(caplog.records, "audiodb.lookup", LOOKUP_REQUIRED_FIELDS)
        assert any("found=true" in m and "entity=album" in m for m in msgs)

    @pytest.mark.asyncio
    async def test_name_search_logs_lookup(self, caplog):
        repo = self._make_repo()
        data = {"artists": [{
            "idArtist": "111239", "strArtist": "Coldplay",
            "strMusicBrainzID": TEST_MBID,
            "strArtistThumb": "https://example.com/thumb.jpg",
        }]}
        repo._client.get = AsyncMock(return_value=self._mock_response(200, data))
        with caplog.at_level("DEBUG"):
            await repo.search_artist_by_name("Coldplay")

        msgs = assert_log_fields(caplog.records, "audiodb.lookup", LOOKUP_REQUIRED_FIELDS)
        assert any("lookup_type=name" in m for m in msgs)




class TestPrewarmLogContract:
    def _make_status_service(self):
        status = MagicMock()
        status.update_phase = AsyncMock()
        status.update_progress = AsyncMock()
        status.persist_progress = AsyncMock()
        status.is_cancelled.return_value = False
        return status

    def _make_precache_service(self, audiodb_svc=None, prefs=None):
        from services.library_precache_service import LibraryPrecacheService

        if audiodb_svc is None:
            audiodb_svc = AsyncMock()
            audiodb_svc.get_cached_artist_images = AsyncMock(return_value=None)
            audiodb_svc.get_cached_album_images = AsyncMock(return_value=None)
            audiodb_svc.fetch_and_cache_artist_images = AsyncMock(return_value=None)
            audiodb_svc.fetch_and_cache_album_images = AsyncMock(return_value=None)
        if prefs is None:
            settings = MagicMock()
            settings.audiodb_enabled = True
            settings.audiodb_name_search_fallback = False
            settings.audiodb_prewarm_concurrency = 4
            settings.audiodb_prewarm_delay = 0.0
            prefs = MagicMock()
            prefs.get_advanced_settings.return_value = settings
        return LibraryPrecacheService(
            lidarr_repo=AsyncMock(),
            cover_repo=AsyncMock(),
            preferences_service=prefs,
            sync_state_store=AsyncMock(),
            genre_index=AsyncMock(),
            library_db=AsyncMock(),
            audiodb_image_service=audiodb_svc,
        )

    @pytest.mark.asyncio
    async def test_prewarm_progress_logs_fire(self, caplog):
        svc = AsyncMock()
        images = AudioDBArtistImages(thumb_url="https://x.com/t.jpg", is_negative=False)
        svc.get_cached_artist_images = AsyncMock(return_value=None)
        svc.get_cached_album_images = AsyncMock(return_value=None)
        svc.fetch_and_cache_artist_images = AsyncMock(return_value=images)
        svc.fetch_and_cache_album_images = AsyncMock(return_value=None)

        precache = self._make_precache_service(audiodb_svc=svc)
        status = self._make_status_service()

        artists = [{"mbid": TEST_MBID, "name": f"Artist{i}"} for i in range(1)]
        with caplog.at_level("DEBUG"):
            with patch.object(precache, '_download_audiodb_bytes', new_callable=AsyncMock, return_value=True):
                await precache._precache_audiodb_data(artists, [], status)

        complete_logs = [
            r.message for r in caplog.records
            if r.message.startswith("audiodb.prewarm") and "action=complete" in r.message
        ]
        assert len(complete_logs) >= 1
        for msg in complete_logs:
            assert "processed=" in msg
            assert "total=" in msg

    @pytest.mark.asyncio
    async def test_prewarm_calls_update_phase_audiodb(self):
        svc = AsyncMock()
        svc.get_cached_artist_images = AsyncMock(return_value=None)
        svc.get_cached_album_images = AsyncMock(return_value=None)
        svc.fetch_and_cache_artist_images = AsyncMock(return_value=None)

        precache = self._make_precache_service(audiodb_svc=svc)
        status = self._make_status_service()

        artists = [{"mbid": TEST_MBID, "name": "Coldplay"}]
        await precache._precache_audiodb_data(artists, [], status)

        phase_calls = [
            c for c in status.update_phase.call_args_list
            if c.args[0] == "audiodb_prewarm"
        ]
        assert len(phase_calls) >= 1, "Expected update_phase('audiodb_prewarm', ...) call"




class TestCacheStatsAudioDBWiring:
    @pytest.mark.asyncio
    async def test_get_stats_includes_audiodb_counts(self):
        from services.cache_service import CacheService

        disk_cache = MagicMock()
        disk_cache.get_stats.return_value = {
            "total_count": 100,
            "album_count": 60,
            "artist_count": 40,
            "audiodb_artist_count": 15,
            "audiodb_album_count": 25,
        }

        mem_cache = MagicMock()
        mem_cache.size.return_value = 10
        mem_cache.estimate_memory_bytes.return_value = 2048

        library_db = AsyncMock()
        library_db.get_stats = AsyncMock(return_value={
            "artist_count": 5,
            "album_count": 8,
            "db_size_bytes": 4096,
        })

        svc = CacheService(
            cache=mem_cache,
            library_db=library_db,
            disk_cache=disk_cache,
        )
        svc._stats_cache_ttl = 0

        with patch("services.cache_service.CACHE_DIR") as mock_dir:
            mock_dir.exists.return_value = False
            stats = await svc.get_stats()

        assert stats.disk_audiodb_artist_count == 15
        assert stats.disk_audiodb_album_count == 25

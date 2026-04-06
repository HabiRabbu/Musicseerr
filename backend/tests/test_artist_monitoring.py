"""Tests for MUS-15B: Artist monitoring API and integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.artist_service import ArtistService
from core.exceptions import ExternalServiceError


@pytest.fixture
def mock_lidarr_repo():
    repo = AsyncMock()
    repo.is_configured = MagicMock(return_value=True)
    repo.get_artist_details.return_value = {
        "id": 42,
        "monitored": False,
        "monitorNewItems": "none",
        "monitor_new_items": "none",
        "name": "Test Artist",
        "overview": "A test artist",
        "genres": ["rock"],
        "links": [],
        "poster_url": None,
        "fanart_url": None,
        "banner_url": None,
    }
    repo.update_artist_monitoring.return_value = {"monitored": False, "auto_download": False}
    repo.get_library_mbids.return_value = set()
    repo.get_artist_albums.return_value = []
    repo.get_requested_mbids.return_value = set()
    return repo


@pytest.fixture
def mock_mb_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_wikidata_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_preferences():
    prefs = MagicMock()
    prefs.get_preferences.return_value = MagicMock(
        primary_types=["Album"],
        secondary_types=[],
    )
    return prefs


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get.return_value = None
    cache.delete.return_value = None
    cache.clear_prefix.return_value = 0
    return cache


@pytest.fixture
def mock_disk_cache():
    return AsyncMock()


@pytest.fixture
def artist_service(
    mock_lidarr_repo, mock_mb_repo, mock_wikidata_repo,
    mock_preferences, mock_cache, mock_disk_cache,
):
    return ArtistService(
        mb_repo=mock_mb_repo,
        lidarr_repo=mock_lidarr_repo,
        wikidata_repo=mock_wikidata_repo,
        preferences_service=mock_preferences,
        memory_cache=mock_cache,
        disk_cache=mock_disk_cache,
    )


class TestSetArtistMonitoring:
    @pytest.mark.asyncio
    async def test_set_monitoring_on(self, artist_service, mock_lidarr_repo, mock_cache):
        result = await artist_service.set_artist_monitoring(
            "abc-123", monitored=True, auto_download=False,
        )
        mock_lidarr_repo.update_artist_monitoring.assert_awaited_once_with(
            "abc-123", monitored=True, monitor_new_items="none",
        )
        mock_cache.delete.assert_awaited()
        assert result == {"monitored": False, "auto_download": False}

    @pytest.mark.asyncio
    async def test_set_monitoring_with_auto_download(self, artist_service, mock_lidarr_repo):
        await artist_service.set_artist_monitoring(
            "abc-123", monitored=True, auto_download=True,
        )
        mock_lidarr_repo.update_artist_monitoring.assert_awaited_once_with(
            "abc-123", monitored=True, monitor_new_items="all",
        )

    @pytest.mark.asyncio
    async def test_auto_download_false_when_unmonitored(self, artist_service, mock_lidarr_repo):
        await artist_service.set_artist_monitoring(
            "abc-123", monitored=False, auto_download=True,
        )
        mock_lidarr_repo.update_artist_monitoring.assert_awaited_once_with(
            "abc-123", monitored=False, monitor_new_items="none",
        )

    @pytest.mark.asyncio
    async def test_raises_when_lidarr_not_configured(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.is_configured = MagicMock(return_value=False)
        with pytest.raises(ExternalServiceError, match="not configured"):
            await artist_service.set_artist_monitoring("abc-123", monitored=True)

    @pytest.mark.asyncio
    async def test_invalidates_artist_cache(self, artist_service, mock_cache):
        await artist_service.set_artist_monitoring("abc-123", monitored=True)
        delete_calls = [str(c) for c in mock_cache.delete.await_args_list]
        assert any("artist_info:abc-123" in c for c in delete_calls)


class TestGetArtistMonitoringStatus:
    @pytest.mark.asyncio
    async def test_returns_status_from_lidarr(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_details.return_value = {
            "id": 42, "monitored": True, "monitor_new_items": "all",
        }
        result = await artist_service.get_artist_monitoring_status("abc-123")
        assert result == {"in_lidarr": True, "monitored": True, "auto_download": True}

    @pytest.mark.asyncio
    async def test_returns_defaults_when_not_in_lidarr(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_details.return_value = None
        result = await artist_service.get_artist_monitoring_status("abc-123")
        assert result == {"in_lidarr": False, "monitored": False, "auto_download": False}

    @pytest.mark.asyncio
    async def test_returns_defaults_when_lidarr_not_configured(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.is_configured = MagicMock(return_value=False)
        result = await artist_service.get_artist_monitoring_status("abc-123")
        assert result == {"in_lidarr": False, "monitored": False, "auto_download": False}


class TestArtistInfoMonitoringFields:
    @pytest.mark.asyncio
    async def test_monitoring_fields_set_from_lidarr(self, artist_service, mock_lidarr_repo, mock_cache):
        mock_lidarr_repo.get_artist_details.return_value = {
            "id": 42,
            "monitored": True,
            "monitor_new_items": "all",
            "name": "Test Artist",
            "overview": "A test artist",
            "genres": ["rock"],
            "links": [],
            "poster_url": None,
            "fanart_url": None,
            "banner_url": None,
        }
        info = await artist_service._do_get_artist_info("abc-123", None, None)
        assert info.monitored is True
        assert info.auto_download is True
        assert info.in_lidarr is True

    @pytest.mark.asyncio
    async def test_monitoring_fields_default_when_no_lidarr(self, artist_service, mock_lidarr_repo, mock_cache):
        mock_lidarr_repo.is_configured = MagicMock(return_value=False)
        mock_lidarr_repo.get_artist_details.return_value = None

        with patch.object(artist_service, '_build_artist_from_musicbrainz') as mock_build:
            from models.artist import ArtistInfo
            mock_build.return_value = ArtistInfo(
                name="Test", musicbrainz_id="abc-123",
                tags=[], aliases=[], external_links=[],
            )
            info = await artist_service._do_get_artist_info("abc-123", None, None)
            assert info.monitored is False
            assert info.auto_download is False
            assert info.in_lidarr is False

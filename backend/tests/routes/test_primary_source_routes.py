import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.schemas.settings import PrimaryMusicSourceSettings
from api.v1.routes.settings import router


@pytest.fixture
def mock_prefs():
    mock = MagicMock()
    mock.get_primary_music_source.return_value = PrimaryMusicSourceSettings(source="listenbrainz")
    mock.save_primary_music_source = MagicMock()
    return mock


@pytest.fixture
def mock_settings_service():
    mock = MagicMock()
    mock.clear_home_cache = AsyncMock(return_value=5)
    return mock


@pytest.fixture
def client(mock_prefs, mock_settings_service):
    app = FastAPI()
    app.include_router(router)
    with (
        patch(
            "api.v1.routes.settings.get_preferences_service",
            return_value=mock_prefs,
        ),
        patch(
            "api.v1.routes.settings.get_settings_service",
            return_value=mock_settings_service,
        ),
    ):
        yield TestClient(app)


class TestGetPrimarySource:
    def test_returns_current_source(self, client, mock_prefs):
        resp = client.get("/api/settings/primary-source")
        assert resp.status_code == 200
        assert resp.json()["source"] == "listenbrainz"

    def test_returns_lastfm_when_configured(self, client, mock_prefs):
        mock_prefs.get_primary_music_source.return_value = PrimaryMusicSourceSettings(
            source="lastfm"
        )
        resp = client.get("/api/settings/primary-source")
        assert resp.status_code == 200
        assert resp.json()["source"] == "lastfm"


class TestUpdatePrimarySource:
    def test_updates_to_lastfm(self, client, mock_prefs):
        mock_prefs.get_primary_music_source.return_value = PrimaryMusicSourceSettings(
            source="lastfm"
        )
        resp = client.put(
            "/api/settings/primary-source",
            json={"source": "lastfm"},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "lastfm"
        mock_prefs.save_primary_music_source.assert_called_once()

    def test_updates_to_listenbrainz(self, client, mock_prefs):
        resp = client.put(
            "/api/settings/primary-source",
            json={"source": "listenbrainz"},
        )
        assert resp.status_code == 200
        mock_prefs.save_primary_music_source.assert_called_once()

    def test_rejects_invalid_source(self, client, mock_prefs):
        resp = client.put(
            "/api/settings/primary-source",
            json={"source": "invalid"},
        )
        assert resp.status_code == 422
        mock_prefs.save_primary_music_source.assert_not_called()

    def test_clears_cache_on_update(self, client, mock_prefs, mock_settings_service):
        resp = client.put(
            "/api/settings/primary-source",
            json={"source": "lastfm"},
        )
        assert resp.status_code == 200
        mock_settings_service.clear_home_cache.assert_awaited_once()

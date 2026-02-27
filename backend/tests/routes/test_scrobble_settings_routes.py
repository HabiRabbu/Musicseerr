import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.routes.settings import router
from api.v1.schemas.settings import ScrobbleSettings
from core.exceptions import ConfigurationError


def _default_scrobble_settings() -> ScrobbleSettings:
    return ScrobbleSettings(scrobble_to_lastfm=True, scrobble_to_listenbrainz=False)


@pytest.fixture
def mock_prefs():
    mock = MagicMock()
    mock.get_scrobble_settings.return_value = _default_scrobble_settings()
    mock.save_scrobble_settings = MagicMock()
    return mock


@pytest.fixture
def client(mock_prefs):
    app = FastAPI()
    app.include_router(router)
    with patch(
        "api.v1.routes.settings.get_preferences_service",
        return_value=mock_prefs,
    ):
        yield TestClient(app)


class TestGetScrobbleSettings:
    def test_returns_settings(self, client):
        resp = client.get("/api/settings/scrobble")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scrobble_to_lastfm"] is True
        assert data["scrobble_to_listenbrainz"] is False

    def test_server_error(self, client, mock_prefs):
        mock_prefs.get_scrobble_settings.side_effect = RuntimeError("boom")
        resp = client.get("/api/settings/scrobble")
        assert resp.status_code == 500


class TestUpdateScrobbleSettings:
    def test_saves_and_returns(self, client, mock_prefs):
        updated = ScrobbleSettings(scrobble_to_lastfm=False, scrobble_to_listenbrainz=True)
        mock_prefs.get_scrobble_settings.return_value = updated
        resp = client.put(
            "/api/settings/scrobble",
            json={"scrobble_to_lastfm": False, "scrobble_to_listenbrainz": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scrobble_to_lastfm"] is False
        assert data["scrobble_to_listenbrainz"] is True
        mock_prefs.save_scrobble_settings.assert_called_once()

    def test_config_error_returns_400(self, client, mock_prefs):
        mock_prefs.save_scrobble_settings.side_effect = ConfigurationError("bad")
        resp = client.put(
            "/api/settings/scrobble",
            json={"scrobble_to_lastfm": True, "scrobble_to_listenbrainz": True},
        )
        assert resp.status_code == 400

    def test_server_error_returns_500(self, client, mock_prefs):
        mock_prefs.save_scrobble_settings.side_effect = RuntimeError("disk full")
        resp = client.put(
            "/api/settings/scrobble",
            json={"scrobble_to_lastfm": True, "scrobble_to_listenbrainz": True},
        )
        assert resp.status_code == 500

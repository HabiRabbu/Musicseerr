import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.schemas.settings import (
    LastFmConnectionSettings,
    LastFmConnectionSettingsResponse,
    LastFmVerifyResponse,
    LASTFM_SECRET_MASK,
    _mask_secret,
)
from api.v1.routes.settings import router


def _saved_settings() -> LastFmConnectionSettings:
    return LastFmConnectionSettings(
        api_key="real-key",
        shared_secret="real-secret-value",
        session_key="sk-real-session",
        username="testuser",
        enabled=True,
    )


@pytest.fixture
def mock_prefs():
    mock = MagicMock()
    mock.get_lastfm_connection.return_value = _saved_settings()
    mock.save_lastfm_connection = MagicMock()
    return mock


@pytest.fixture
def mock_settings_service():
    mock = MagicMock()
    mock.clear_home_cache = AsyncMock()
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
        patch(
            "api.v1.routes.settings.get_lastfm_repository",
            MagicMock(cache_clear=MagicMock()),
        ),
        patch(
            "api.v1.routes.settings.get_lastfm_auth_service",
            MagicMock(cache_clear=MagicMock()),
        ),
        patch.object(
            __import__("repositories.lastfm_repository", fromlist=["LastFmRepository"]).LastFmRepository,
            "reset_circuit_breaker",
        ),
    ):
        yield TestClient(app)


class TestGetLastFmSettings:
    def test_returns_masked_secrets(self, client, mock_prefs):
        response = client.get("/api/settings/lastfm")
        assert response.status_code == 200
        data = response.json()
        assert data["api_key"] == "real-key"
        assert data["shared_secret"] == _mask_secret("real-secret-value")
        assert data["session_key"] == _mask_secret("sk-real-session")
        assert data["username"] == "testuser"
        assert data["enabled"] is True

    def test_returns_empty_when_no_secret(self, client, mock_prefs):
        mock_prefs.get_lastfm_connection.return_value = LastFmConnectionSettings()
        response = client.get("/api/settings/lastfm")
        assert response.status_code == 200
        data = response.json()
        assert data["shared_secret"] == ""
        assert data["session_key"] == ""


class TestPutLastFmSettings:
    def test_save_returns_masked_response(self, client, mock_prefs):
        response = client.put(
            "/api/settings/lastfm",
            json={
                "api_key": "new-key",
                "shared_secret": "new-secret",
                "session_key": "",
                "username": "",
                "enabled": True,
            },
        )
        assert response.status_code == 200
        mock_prefs.save_lastfm_connection.assert_called_once()
        data = response.json()
        assert data["shared_secret"] == _mask_secret("real-secret-value")

    def test_save_with_empty_creds_still_succeeds(self, client, mock_prefs):
        mock_prefs.get_lastfm_connection.return_value = LastFmConnectionSettings(
            api_key="",
            shared_secret="",
            session_key="",
            username="",
            enabled=False,
        )
        response = client.put(
            "/api/settings/lastfm",
            json={
                "api_key": "",
                "shared_secret": "",
                "session_key": "",
                "username": "",
                "enabled": False,
            },
        )
        assert response.status_code == 200

    def test_save_preserves_masked_session_key(self, client, mock_prefs):
        masked = _mask_secret("sk-real-session")
        response = client.put(
            "/api/settings/lastfm",
            json={
                "api_key": "real-key",
                "shared_secret": LASTFM_SECRET_MASK,
                "session_key": masked,
                "username": "testuser",
                "enabled": True,
            },
        )
        assert response.status_code == 200
        saved = mock_prefs.save_lastfm_connection.call_args[0][0]
        assert saved.shared_secret == LASTFM_SECRET_MASK
        assert saved.session_key == masked


class TestMaskSecretConsistency:
    def test_mask_secret_starts_with_mask_constant(self):
        masked = _mask_secret("secret123")
        assert masked.startswith(LASTFM_SECRET_MASK)

    def test_mask_secret_short_value_equals_mask(self):
        masked = _mask_secret("ab")
        assert masked == LASTFM_SECRET_MASK

    def test_mask_secret_empty_returns_empty(self):
        assert _mask_secret("") == ""

    def test_mask_secret_suffix_preserved(self):
        masked = _mask_secret("my-long-secret")
        assert masked == LASTFM_SECRET_MASK + "cret"

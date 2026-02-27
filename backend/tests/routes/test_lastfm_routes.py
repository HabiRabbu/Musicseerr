import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.schemas.settings import (
    LastFmConnectionSettings,
)
from api.v1.routes.lastfm import router as lastfm_router
from core.dependencies import (
    get_lastfm_auth_service,
    get_preferences_service,
)
from core.exceptions import ConfigurationError, ExternalServiceError, TokenNotAuthorizedError


def _default_settings() -> LastFmConnectionSettings:
    return LastFmConnectionSettings(
        api_key="test-key",
        shared_secret="test-secret",
        session_key="sk-abc",
        username="testuser",
        enabled=True,
    )


@pytest.fixture
def mock_preferences():
    mock = MagicMock()
    mock.get_lastfm_connection.return_value = _default_settings()
    mock.save_lastfm_connection = MagicMock()
    mock.is_lastfm_enabled.return_value = True
    return mock


@pytest.fixture
def mock_auth_service():
    mock = AsyncMock()
    mock.request_token = AsyncMock(
        return_value=("tok-123", "https://www.last.fm/api/auth/?api_key=test-key&token=tok-123")
    )
    mock.exchange_session = AsyncMock(return_value=("testuser", "sk-new", ""))
    return mock


@pytest.fixture
def auth_client(mock_preferences, mock_auth_service):
    app = FastAPI()
    app.include_router(lastfm_router)
    app.dependency_overrides[get_preferences_service] = lambda: mock_preferences
    app.dependency_overrides[get_lastfm_auth_service] = lambda: mock_auth_service
    return TestClient(app)


def test_request_token_success(auth_client, mock_auth_service):
    response = auth_client.post("/api/lastfm/auth/token")
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "tok-123"
    assert "auth_url" in data


def test_request_token_missing_credentials(auth_client, mock_preferences):
    mock_preferences.get_lastfm_connection.return_value = LastFmConnectionSettings(
        api_key="", shared_secret="", session_key="", username="", enabled=False
    )
    response = auth_client.post("/api/lastfm/auth/token")
    assert response.status_code == 400


def test_request_token_external_error(auth_client, mock_auth_service):
    mock_auth_service.request_token.side_effect = ExternalServiceError("Last.fm down")
    response = auth_client.post("/api/lastfm/auth/token")
    assert response.status_code == 502


def test_exchange_session_success(auth_client, mock_auth_service, mock_preferences):
    response = auth_client.post(
        "/api/lastfm/auth/session",
        json={"token": "tok-123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["username"] == "testuser"
    mock_preferences.save_lastfm_connection.assert_called_once()


def test_exchange_session_expired_token(auth_client, mock_auth_service):
    mock_auth_service.exchange_session.side_effect = ConfigurationError(
        "Token expired or not recognized"
    )
    response = auth_client.post(
        "/api/lastfm/auth/session",
        json={"token": "expired-tok"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "expired" in data["detail"].lower()


def test_exchange_session_external_error(auth_client, mock_auth_service):
    mock_auth_service.exchange_session.side_effect = ExternalServiceError(
        "Last.fm unreachable"
    )
    response = auth_client.post(
        "/api/lastfm/auth/session",
        json={"token": "tok-123"},
    )
    assert response.status_code == 502
    data = response.json()
    assert "detail" in data


def test_exchange_session_token_not_authorized(auth_client, mock_auth_service):
    mock_auth_service.exchange_session.side_effect = TokenNotAuthorizedError(
        "Token not yet authorized"
    )
    response = auth_client.post(
        "/api/lastfm/auth/session",
        json={"token": "tok-pending"},
    )
    assert response.status_code == 502
    data = response.json()
    assert "authorize" in data["detail"].lower()

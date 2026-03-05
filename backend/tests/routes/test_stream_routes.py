from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.routes.stream import router
from core.dependencies import get_jellyfin_playback_service, get_jellyfin_repository
from core.exceptions import ExternalServiceError, PlaybackNotAllowedError, ResourceNotFoundError
from repositories.jellyfin_models import PlaybackUrlResult


@pytest.fixture
def mock_jellyfin_repo():
    mock = MagicMock()
    mock.get_playback_url = AsyncMock(
        return_value=PlaybackUrlResult(
            url="http://jellyfin:8096/Audio/item-1/stream?static=true&api_key=test-key",
            seekable=True,
            play_session_id="sess-1",
            play_method="DirectPlay",
        )
    )
    return mock


@pytest.fixture
def mock_playback_service():
    mock = MagicMock()
    mock.start_playback = AsyncMock(return_value="sess-start")
    return mock


@pytest.fixture
def client(mock_jellyfin_repo, mock_playback_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_jellyfin_repository] = lambda: mock_jellyfin_repo
    app.dependency_overrides[get_jellyfin_playback_service] = lambda: mock_playback_service
    return TestClient(app)


def test_get_stream_returns_json_with_seekable_and_session(client):
    response = client.get("/api/stream/jellyfin/item-1")

    assert response.status_code == 200
    assert response.json() == {
        "url": "http://jellyfin:8096/Audio/item-1/stream?static=true&api_key=test-key",
        "seekable": True,
        "playSessionId": "sess-1",
    }


def test_get_stream_transcode_returns_non_seekable(client, mock_jellyfin_repo):
    mock_jellyfin_repo.get_playback_url = AsyncMock(
        return_value=PlaybackUrlResult(
            url="http://jellyfin:8096/Audio/item-2/universal?container=opus",
            seekable=False,
            play_session_id="sess-2",
            play_method="Transcode",
        )
    )

    response = client.get("/api/stream/jellyfin/item-2")

    assert response.status_code == 200
    assert response.json()["seekable"] is False
    assert "/universal" in response.json()["url"]


def test_get_stream_returns_404_when_item_missing(client, mock_jellyfin_repo):
    mock_jellyfin_repo.get_playback_url.side_effect = ResourceNotFoundError("missing")

    response = client.get("/api/stream/jellyfin/missing-item")

    assert response.status_code == 404


def test_get_stream_returns_403_when_playback_not_allowed(client, mock_jellyfin_repo):
    mock_jellyfin_repo.get_playback_url.side_effect = PlaybackNotAllowedError("NotAllowed")

    response = client.get("/api/stream/jellyfin/item-denied")

    assert response.status_code == 403


def test_get_stream_returns_502_on_external_error(client, mock_jellyfin_repo):
    mock_jellyfin_repo.get_playback_url.side_effect = ExternalServiceError("jellyfin down")

    response = client.get("/api/stream/jellyfin/item-err")

    assert response.status_code == 502


def test_head_stream_returns_redirect(client):
    response = client.request("HEAD", "/api/stream/jellyfin/item-1", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "http://jellyfin:8096/Audio/item-1/stream?static=true&api_key=test-key"


def test_head_stream_sets_no_referrer_policy(client):
    response = client.request("HEAD", "/api/stream/jellyfin/item-1", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["referrer-policy"] == "no-referrer"


def test_start_stream_uses_existing_play_session_id(client, mock_playback_service):
    response = client.post(
        "/api/stream/jellyfin/item-1/start",
        json={"play_session_id": "sess-existing"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "play_session_id": "sess-start",
        "item_id": "item-1",
    }
    mock_playback_service.start_playback.assert_awaited_once_with(
        "item-1",
        play_session_id="sess-existing",
    )


def test_start_stream_without_payload_uses_service_default(client, mock_playback_service):
    response = client.post("/api/stream/jellyfin/item-2/start")

    assert response.status_code == 200
    assert response.json()["item_id"] == "item-2"
    mock_playback_service.start_playback.assert_awaited_once_with(
        "item-2",
        play_session_id=None,
    )

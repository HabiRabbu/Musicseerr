import os
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure config uses a writable temp dir for tests
_test_dir = tempfile.mkdtemp()
os.environ.setdefault("ROOT_APP_DIR", _test_dir)


VALID_MBID = "77434d0b-1c5f-48c3-8694-050cb378ebd2"
UNKNOWN_MBID = "00000000-0000-0000-0000-000000000000"


def _make_basic_info():
    return MagicMock(
        release_group_id=VALID_MBID,
        title="Test Album",
        artist_name="Test Artist",
        in_library=True,
    )


@pytest.fixture
def mock_album_service():
    svc = MagicMock()
    svc.refresh_album = AsyncMock()
    svc.get_album_basic_info = AsyncMock(return_value=_make_basic_info())
    return svc


@pytest.fixture
def mock_navidrome_service():
    svc = MagicMock()
    svc.invalidate_album_cache = MagicMock()
    return svc


@pytest.fixture
def client(mock_album_service, mock_navidrome_service):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.v1.routes.albums import router
    from core.dependencies import get_album_service, get_navidrome_library_service

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_album_service] = lambda: mock_album_service
    app.dependency_overrides[get_navidrome_library_service] = lambda: mock_navidrome_service
    return TestClient(app)


def test_refresh_calls_invalidate_and_refresh(client, mock_album_service, mock_navidrome_service):
    response = client.post(f"/albums/{VALID_MBID}/refresh")

    assert response.status_code == 200
    mock_navidrome_service.invalidate_album_cache.assert_called_once_with(VALID_MBID)
    mock_album_service.refresh_album.assert_called_once_with(VALID_MBID)
    mock_album_service.get_album_basic_info.assert_called_once_with(VALID_MBID)


def test_refresh_returns_basic_info(client):
    response = client.post(f"/albums/{VALID_MBID}/refresh")

    assert response.status_code == 200


def test_refresh_rejects_unknown_mbid(client, mock_album_service, mock_navidrome_service):
    response = client.post("/albums/unknown_test/refresh")

    assert response.status_code == 400
    assert "Invalid or unknown" in response.json()["detail"]
    mock_album_service.refresh_album.assert_not_called()
    mock_navidrome_service.invalidate_album_cache.assert_not_called()


def test_refresh_rejects_empty_album_id(client, mock_album_service):
    response = client.post("/albums/%20/refresh")

    assert response.status_code == 400
    mock_album_service.refresh_album.assert_not_called()


def test_refresh_propagates_service_value_error(client, mock_album_service, mock_navidrome_service):
    mock_navidrome_service.invalidate_album_cache = MagicMock(side_effect=ValueError("bad"))

    response = client.post(f"/albums/{VALID_MBID}/refresh")

    assert response.status_code == 400

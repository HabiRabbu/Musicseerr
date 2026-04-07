import os
import tempfile

os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.routes.artists import router
from api.v1.schemas.artist import ArtistReleases
from core.dependencies import get_artist_service, get_artist_discovery_service, get_artist_enrichment_service
from models.artist import ReleaseItem


VALID_MBID = "f4a31f0a-51dd-4fa7-986d-3095c40c5ed9"


@pytest.fixture
def mock_artist_service():
    mock = AsyncMock()
    mock.get_artist_releases = AsyncMock(
        return_value=ArtistReleases(
            albums=[ReleaseItem(id="rg-2", title="Album Two", type="Album", year=2023)],
            singles=[],
            eps=[],
            total_count=120,
            has_more=True,
        )
    )
    mock.get_artist_info_basic = AsyncMock()
    return mock


@pytest.fixture
def mock_discovery_service():
    return AsyncMock()


@pytest.fixture
def mock_enrichment_service():
    return AsyncMock()


@pytest.fixture
def client(mock_artist_service, mock_discovery_service, mock_enrichment_service):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_artist_service] = lambda: mock_artist_service
    app.dependency_overrides[get_artist_discovery_service] = lambda: mock_discovery_service
    app.dependency_overrides[get_artist_enrichment_service] = lambda: mock_enrichment_service
    return TestClient(app)


class TestGetArtistReleasesRoute:
    def test_pagination_params_forwarded(self, client, mock_artist_service):
        response = client.get(f"/api/v1/artists/{VALID_MBID}/releases?offset=50&limit=50")

        assert response.status_code == 200
        mock_artist_service.get_artist_releases.assert_awaited_once_with(VALID_MBID, 50, 50)

    def test_has_more_flag_propagated(self, client):
        response = client.get(f"/api/v1/artists/{VALID_MBID}/releases?offset=0&limit=50")
        body = response.json()

        assert response.status_code == 200
        assert body["has_more"] is True
        assert body["total_count"] == 120

    def test_default_params(self, client, mock_artist_service):
        response = client.get(f"/api/v1/artists/{VALID_MBID}/releases")

        assert response.status_code == 200
        mock_artist_service.get_artist_releases.assert_awaited_once_with(VALID_MBID, 0, 50)

    def test_value_error_returns_400(self, client, mock_artist_service):
        mock_artist_service.get_artist_releases = AsyncMock(
            side_effect=ValueError("Invalid artist request")
        )
        response = client.get(f"/api/v1/artists/{VALID_MBID}/releases")
        assert response.status_code == 400

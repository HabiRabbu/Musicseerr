"""Route-level tests for POST /api/v1/discover/radio."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.v1.schemas.home import HomeAlbum, HomeSection
from api.v1.routes.discover import router
from core.dependencies import get_discover_service


def _make_radio_section(source: str = "listenbrainz", count: int = 3) -> HomeSection:
    return HomeSection(
        title="Radio: Test Artist",
        type="albums",
        items=[
            HomeAlbum(
                name=f"Album {i}",
                mbid=f"rg-mbid-{i}",
                artist_name="Test Artist",
                artist_mbid="artist-mbid-1",
                image_url=f"/api/v1/covers/release-group/rg-mbid-{i}?size=500",
            )
            for i in range(count)
        ],
        source=source,
    )


@pytest.fixture
def mock_discover_service():
    mock = AsyncMock()
    mock.generate_radio = AsyncMock(return_value=_make_radio_section())
    mock.resolve_source = MagicMock(side_effect=lambda s: s or "listenbrainz")
    return mock


@pytest.fixture
def client(mock_discover_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_discover_service] = lambda: mock_discover_service
    return TestClient(app)


class TestPostRadioValidArtistSeed:
    def test_returns_200(self, client, mock_discover_service) -> None:
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "artist", "seed_id": "valid-mbid"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "albums"
        assert data["title"].startswith("Radio: ")
        assert len(data["items"]) == 3


class TestPostRadioInvalidSeedType:
    def test_returns_422(self, client) -> None:
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "invalid", "seed_id": "x"},
        )
        assert resp.status_code == 422


class TestPostRadioEmptySeedId:
    def test_returns_400(self, client, mock_discover_service) -> None:
        mock_discover_service.generate_radio = AsyncMock(
            side_effect=HTTPException(status_code=400, detail="seed_id must be non-empty"),
        )
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "artist", "seed_id": ""},
        )
        assert resp.status_code == 400


class TestPostRadioUnknownArtistMbid:
    def test_returns_404(self, client, mock_discover_service) -> None:
        mock_discover_service.generate_radio = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Unknown artist MBID"),
        )
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "artist", "seed_id": "unknown-mbid"},
        )
        assert resp.status_code == 404


class TestPostRadioUnknownGenreTag:
    def test_returns_422(self, client, mock_discover_service) -> None:
        mock_discover_service.generate_radio = AsyncMock(
            side_effect=HTTPException(status_code=422, detail="Unknown genre tag"),
        )
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "genre", "seed_id": "nonexistent"},
        )
        assert resp.status_code == 422


class TestPostRadioWithOptionalCount:
    def test_returns_200_with_count(self, client, mock_discover_service) -> None:
        mock_discover_service.generate_radio = AsyncMock(
            return_value=_make_radio_section(count=5),
        )
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "artist", "seed_id": "x", "count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5


class TestPostRadioWithOptionalSource:
    def test_returns_200_with_source(self, client, mock_discover_service) -> None:
        mock_discover_service.generate_radio = AsyncMock(
            return_value=_make_radio_section(source="lastfm"),
        )
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "artist", "seed_id": "x", "source": "lastfm"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "lastfm"


class TestPostRadioMissingSeedType:
    def test_returns_422(self, client) -> None:
        resp = client.post(
            "/discover/radio",
            json={"seed_id": "x"},
        )
        assert resp.status_code == 422


class TestPostRadioInvalidSource:
    def test_returns_422_for_invalid_source(self, client) -> None:
        resp = client.post(
            "/discover/radio",
            json={"seed_type": "artist", "seed_id": "x", "source": "spotify"},
        )
        assert resp.status_code == 422

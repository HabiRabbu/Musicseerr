import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.routes.home import router
from core.dependencies import get_home_charts_service, get_home_service


@pytest.fixture
def mock_home_service():
    mock = AsyncMock()
    mock.get_home_data = AsyncMock(
        return_value={
            'recently_added': None,
            'library_artists': None,
            'library_albums': None,
            'recommended_artists': None,
            'trending_artists': None,
            'popular_albums': None,
            'recently_played': None,
            'top_genres': None,
            'genre_list': None,
            'fresh_releases': None,
            'favorite_artists': None,
            'service_prompts': [],
            'integration_status': {},
            'genre_artists': {},
            'discover_preview': None,
        }
    )
    return mock


@pytest.fixture
def mock_charts_service():
    mock = AsyncMock()
    mock.get_trending_artists_by_range = AsyncMock(
        return_value={
            'range_key': 'this_week',
            'label': 'This Week',
            'items': [],
            'offset': 0,
            'limit': 25,
            'has_more': False,
        }
    )
    mock.get_popular_albums_by_range = AsyncMock(
        return_value={
            'range_key': 'this_week',
            'label': 'This Week',
            'items': [],
            'offset': 0,
            'limit': 25,
            'has_more': False,
        }
    )
    return mock


@pytest.fixture
def client(mock_home_service, mock_charts_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_home_service] = lambda: mock_home_service
    app.dependency_overrides[get_home_charts_service] = lambda: mock_charts_service
    return TestClient(app)


class TestHomeRangeSourcePropagation:
    def test_trending_range_forwards_lastfm_source(self, client, mock_charts_service):
        response = client.get('/api/home/trending/artists/this_week?limit=10&offset=5&source=lastfm')

        assert response.status_code == 200
        mock_charts_service.get_trending_artists_by_range.assert_awaited_once_with(
            range_key='this_week',
            limit=10,
            offset=5,
            source='lastfm',
        )

    def test_trending_range_forwards_none_source_when_missing(self, client, mock_charts_service):
        response = client.get('/api/home/trending/artists/this_week?limit=10&offset=0')

        assert response.status_code == 200
        mock_charts_service.get_trending_artists_by_range.assert_awaited_once_with(
            range_key='this_week',
            limit=10,
            offset=0,
            source=None,
        )

    def test_popular_range_forwards_listenbrainz_source(self, client, mock_charts_service):
        response = client.get('/api/home/popular/albums/this_month?limit=12&offset=3&source=listenbrainz')

        assert response.status_code == 200
        mock_charts_service.get_popular_albums_by_range.assert_awaited_once_with(
            range_key='this_month',
            limit=12,
            offset=3,
            source='listenbrainz',
        )

    def test_popular_range_forwards_none_source_when_missing(self, client, mock_charts_service):
        response = client.get('/api/home/popular/albums/this_year?limit=8&offset=1')

        assert response.status_code == 200
        mock_charts_service.get_popular_albums_by_range.assert_awaited_once_with(
            range_key='this_year',
            limit=8,
            offset=1,
            source=None,
        )

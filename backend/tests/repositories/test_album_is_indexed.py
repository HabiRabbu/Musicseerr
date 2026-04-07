"""Test that album_is_indexed returns a dict, not an int.

Regression test for: 'argument of type int is not iterable' when
album_is_indexed returned a.get("id") (int) instead of the album dict.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from repositories.lidarr.album import LidarrAlbumRepository


@pytest.fixture
def album_repo():
    settings = MagicMock()
    settings.lidarr_url = "http://lidarr:8686"
    settings.lidarr_api_key = "test-key"
    settings.quality_profile_id = 1
    cache = AsyncMock()
    cache.get.return_value = None
    cache.set.return_value = None
    cache.delete.return_value = None
    cache.clear_prefix.return_value = 0
    http_client = AsyncMock()
    return LidarrAlbumRepository(settings=settings, http_client=http_client, cache=cache)


class TestAlbumIsIndexedReturnType:
    """The album_is_indexed closure must return a dict (or None), never an int."""

    @pytest.mark.asyncio
    async def test_add_album_new_album_existing_artist_no_type_error(self, album_repo):
        """When album needs POST-adding for an existing artist, album_obj must be a dict.

        Before the fix, album_is_indexed returned a.get("id") (int),
        causing 'argument of type int is not iterable' at the 'id not in album_obj' check.
        """
        artist_repo = AsyncMock()
        artist_repo._ensure_artist_exists.return_value = (
            {"id": 42, "artistName": "MCR", "foreignArtistId": "artist-1",
             "qualityProfileId": 1, "metadataProfileId": 1, "rootFolderPath": "/music"},
            False,  # artist NOT created (already existed)
        )

        album_dict = {
            "id": 99,
            "title": "Greatest Hits",
            "foreignAlbumId": "ae700a64-0890-457e-9440-51cdb06d58e1",
            "monitored": True,
            "statistics": {"trackFileCount": 0},
            "artist": {"foreignArtistId": "artist-1", "artistName": "MCR"},
        }

        lookup_response = [{
            "foreignAlbumId": "ae700a64-0890-457e-9440-51cdb06d58e1",
            "title": "Greatest Hits",
            "albumType": "Album",
            "secondaryTypes": [],
            "artist": {"mbId": "artist-1", "foreignArtistId": "artist-1", "artistName": "MCR"},
        }]

        album_repo._get = AsyncMock(side_effect=[
            lookup_response,       # album/lookup
            [{"id": 42}],          # /api/v1/artist (existing artist check)
            [album_dict],          # /api/v1/album?artistId=42 (pre_add_monitored_ids)
            [{"id": 1}],           # /api/v1/qualityprofile
            album_dict,            # POST /api/v1/album response (via _post)
            [album_dict],          # /api/v1/album?artistId=42 (unmonitor check)
        ])

        # First call: not found. Second call onward: found (after POST).
        album_repo._get_album_by_foreign_id = AsyncMock(side_effect=[
            None,        # initial check — album not in Lidarr yet
            album_dict,  # after POST — album now indexed
            album_dict,  # final fetch
        ])
        album_repo._post = AsyncMock(return_value=album_dict)
        album_repo._put = AsyncMock(return_value=album_dict)

        result = await album_repo.add_album(
            "ae700a64-0890-457e-9440-51cdb06d58e1", artist_repo
        )

        assert isinstance(result, dict)
        assert "payload" in result
        payload = result["payload"]
        assert isinstance(payload, dict), (
            f"payload should be dict, got {type(payload).__name__}. "
            "This was the original bug — album_is_indexed returned int."
        )
        assert payload.get("id") == 99

    @pytest.mark.asyncio
    async def test_add_album_existing_album_no_regression(self, album_repo):
        """Existing monitored+downloaded album returns immediately (no type error)."""
        artist_repo = AsyncMock()
        artist_repo._ensure_artist_exists.return_value = (
            {"id": 42, "artistName": "MCR", "foreignArtistId": "artist-1",
             "qualityProfileId": 1, "metadataProfileId": 1, "rootFolderPath": "/music"},
            False,
        )

        album_dict = {
            "id": 50,
            "title": "Three Cheers",
            "foreignAlbumId": "bbbb-cccc",
            "monitored": True,
            "statistics": {"trackFileCount": 12},
            "artist": {"foreignArtistId": "artist-1"},
        }

        album_repo._get = AsyncMock(side_effect=[
            [{"foreignAlbumId": "bbbb-cccc", "title": "Three Cheers", "albumType": "Album",
              "secondaryTypes": [],
              "artist": {"mbId": "artist-1", "foreignArtistId": "artist-1", "artistName": "MCR"}}],
            [{"id": 42}],  # existing artist
            [album_dict],  # albums_before for pre_add_monitored_ids
        ])
        album_repo._get_album_by_foreign_id = AsyncMock(return_value=album_dict)
        album_repo._put = AsyncMock()
        album_repo._post = AsyncMock()

        result = await album_repo.add_album("bbbb-cccc", artist_repo)

        assert isinstance(result, dict)
        assert "already downloaded" in result["message"]
        assert isinstance(result["payload"], dict)

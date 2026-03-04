from unittest.mock import AsyncMock, MagicMock

import pytest

from api.v1.schemas.album import AlbumInfo
from services.album_service import AlbumService


def _make_service() -> tuple[AlbumService, MagicMock, MagicMock]:
    lidarr_repo = MagicMock()
    mb_repo = MagicMock()
    library_cache = MagicMock()
    memory_cache = MagicMock()
    disk_cache = MagicMock()
    preferences_service = MagicMock()

    service = AlbumService(
        lidarr_repo=lidarr_repo,
        mb_repo=mb_repo,
        library_cache=library_cache,
        memory_cache=memory_cache,
        disk_cache=disk_cache,
        preferences_service=preferences_service,
    )
    return service, lidarr_repo, library_cache


@pytest.mark.asyncio
async def test_revalidate_library_status_keeps_value_when_lidarr_details_unavailable():
    service, lidarr_repo, _ = _make_service()
    lidarr_repo.get_album_details = AsyncMock(return_value=None)
    lidarr_repo.get_library_mbids = AsyncMock(return_value={"should-not-be-used"})
    service._save_album_to_cache = AsyncMock()

    album_info = AlbumInfo(
        title="Test",
        musicbrainz_id="4549a80c-efe6-4386-b3a2-4b4a918eb31f",
        artist_name="Artist",
        artist_id="artist-id",
        in_library=True,
    )

    result = await service._revalidate_library_status(album_info.musicbrainz_id, album_info)

    assert result.in_library is True
    service._save_album_to_cache.assert_not_called()
    lidarr_repo.get_library_mbids.assert_not_called()


@pytest.mark.asyncio
async def test_revalidate_library_status_uses_lidarr_details_and_updates_cache_on_change():
    service, lidarr_repo, _ = _make_service()
    lidarr_repo.get_album_details = AsyncMock(
        return_value={"monitored": False, "statistics": {"trackFileCount": 0}}
    )
    service._save_album_to_cache = AsyncMock()

    album_info = AlbumInfo(
        title="Test",
        musicbrainz_id="8e1e9e51-38dc-4df3-8027-a0ada37d4674",
        artist_name="Artist",
        artist_id="artist-id",
        in_library=True,
    )

    result = await service._revalidate_library_status(album_info.musicbrainz_id, album_info)

    assert result.in_library is False
    service._save_album_to_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_album_basic_info_does_not_use_library_cache_when_lidarr_payload_exists():
    service, lidarr_repo, library_cache = _make_service()
    service._get_cached_album_info = AsyncMock(return_value=None)
    service._fetch_release_group = AsyncMock(
        return_value={
            "title": "Album",
            "first-release-date": "2024-01-01",
            "primary-type": "Album",
            "disambiguation": "",
            "artist-credit": [],
        }
    )

    lidarr_repo.get_requested_mbids = AsyncMock(return_value=set())
    lidarr_repo.get_album_details = AsyncMock(
        return_value={"monitored": False, "statistics": {"trackFileCount": 20}}
    )
    library_cache.get_album_by_mbid = AsyncMock(return_value={"mbid": "from-cache"})

    result = await service.get_album_basic_info("8e1e9e51-38dc-4df3-8027-a0ada37d4674")

    assert result.in_library is False
    library_cache.get_album_by_mbid.assert_not_awaited()

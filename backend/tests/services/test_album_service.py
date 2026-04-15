from unittest.mock import AsyncMock, MagicMock

import pytest

from api.v1.schemas.album import AlbumInfo
from services.album_service import AlbumService


def _make_service() -> tuple[AlbumService, MagicMock, MagicMock]:
    lidarr_repo = MagicMock()
    mb_repo = MagicMock()
    library_db = MagicMock()
    memory_cache = MagicMock()
    disk_cache = MagicMock()
    preferences_service = MagicMock()
    audiodb_image_service = MagicMock()

    service = AlbumService(
        lidarr_repo=lidarr_repo,
        mb_repo=mb_repo,
        library_db=library_db,
        memory_cache=memory_cache,
        disk_cache=disk_cache,
        preferences_service=preferences_service,
        audiodb_image_service=audiodb_image_service,
    )
    return service, lidarr_repo, library_db


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
    service, lidarr_repo, library_db = _make_service()
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
    library_db.get_album_by_mbid = AsyncMock(return_value={"mbid": "from-cache"})

    result = await service.get_album_basic_info("8e1e9e51-38dc-4df3-8027-a0ada37d4674")

    assert result.in_library is True
    library_db.get_album_by_mbid.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_album_tracks_info_preserves_disc_numbers_from_lidarr():
    service, lidarr_repo, _ = _make_service()
    service._get_cached_album_info = AsyncMock(return_value=None)
    lidarr_repo.is_configured.return_value = True
    lidarr_repo.get_album_details = AsyncMock(return_value={"id": 42, "monitored": True, "statistics": {"trackFileCount": 1}})
    lidarr_repo.get_album_tracks = AsyncMock(
        return_value=[
            {
                "track_number": 1,
                "disc_number": 1,
                "title": "Disc One",
                "duration_ms": 1000,
            },
            {
                "track_number": 1,
                "disc_number": 2,
                "title": "Disc Two",
                "duration_ms": 2000,
            },
        ]
    )

    result = await service.get_album_tracks_info("8e1e9e51-38dc-4df3-8027-a0ada37d4674")

    assert [(track.disc_number, track.position, track.title) for track in result.tracks] == [
        (1, 1, "Disc One"),
        (2, 1, "Disc Two"),
    ]
    assert result.total_length == 3000


@pytest.mark.asyncio
async def test_get_album_tracks_info_multi_disc_same_track_numbers():
    """Verify tracks with same track_number but different disc_number are kept distinct."""
    service, lidarr_repo, _ = _make_service()
    service._get_cached_album_info = AsyncMock(return_value=None)
    lidarr_repo.is_configured.return_value = True
    lidarr_repo.get_album_details = AsyncMock(return_value={"id": 42, "monitored": True, "statistics": {"trackFileCount": 1}})
    lidarr_repo.get_album_tracks = AsyncMock(
        return_value=[
            {"track_number": 1, "disc_number": 1, "title": "Intro", "duration_ms": 1000},
            {"track_number": 2, "disc_number": 1, "title": "Main", "duration_ms": 2000},
            {"track_number": 1, "disc_number": 2, "title": "Intro II", "duration_ms": 1500},
            {"track_number": 2, "disc_number": 2, "title": "Finale", "duration_ms": 3000},
        ]
    )

    result = await service.get_album_tracks_info("8e1e9e51-38dc-4df3-8027-a0ada37d4674")

    assert len(result.tracks) == 4
    disc_track_pairs = [(track.disc_number, track.position, track.title) for track in result.tracks]
    assert (1, 1, "Intro") in disc_track_pairs
    assert (1, 2, "Main") in disc_track_pairs
    assert (2, 1, "Intro II") in disc_track_pairs
    assert (2, 2, "Finale") in disc_track_pairs
    assert result.total_length == 7500

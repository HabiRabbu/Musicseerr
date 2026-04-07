"""Tests for _refresh_library_flags in_lidarr/monitored/auto_download refresh."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from models.artist import ArtistInfo
from services.artist_service import ArtistService


@pytest.fixture
def mock_lidarr_repo():
    repo = AsyncMock()
    repo.is_configured = MagicMock(return_value=True)
    repo.get_library_mbids.return_value = set()
    repo.get_requested_mbids.return_value = set()
    repo.get_artist_mbids.return_value = set()
    repo.get_artist_details.return_value = None
    return repo


@pytest.fixture
def artist_service(mock_lidarr_repo):
    return ArtistService(
        mb_repo=AsyncMock(),
        lidarr_repo=mock_lidarr_repo,
        wikidata_repo=AsyncMock(),
        preferences_service=MagicMock(),
        memory_cache=AsyncMock(),
        disk_cache=AsyncMock(),
    )


def _make_artist(mbid: str = "aaa-bbb", in_lidarr: bool = False,
                 monitored: bool = False, auto_download: bool = False) -> ArtistInfo:
    return ArtistInfo(
        name="Test Artist",
        musicbrainz_id=mbid,
        in_lidarr=in_lidarr,
        monitored=monitored,
        auto_download=auto_download,
    )


class TestRefreshLibraryFlagsLidarrTransition:
    """When an artist transitions into artist_mbids, in_lidarr/monitored/auto_download should update."""

    @pytest.mark.asyncio
    async def test_transition_sets_in_lidarr_and_monitoring(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_mbids.return_value = {"aaa-bbb"}
        mock_lidarr_repo.get_artist_details.return_value = {
            "monitored": True, "monitor_new_items": "all",
        }
        artist = _make_artist(in_lidarr=False)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_lidarr is True
        assert artist.monitored is True
        assert artist.auto_download is True
        mock_lidarr_repo.get_artist_details.assert_awaited_once_with("aaa-bbb")

    @pytest.mark.asyncio
    async def test_transition_monitored_false_auto_download_none(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_mbids.return_value = {"aaa-bbb"}
        mock_lidarr_repo.get_artist_details.return_value = {
            "monitored": False, "monitor_new_items": "none",
        }
        artist = _make_artist(in_lidarr=False)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_lidarr is True
        assert artist.monitored is False
        assert artist.auto_download is False

    @pytest.mark.asyncio
    async def test_transition_details_none_still_sets_in_lidarr(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_mbids.return_value = {"aaa-bbb"}
        mock_lidarr_repo.get_artist_details.return_value = None
        artist = _make_artist(in_lidarr=False)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_lidarr is True

    @pytest.mark.asyncio
    async def test_transition_details_exception_graceful_degradation(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_mbids.return_value = {"aaa-bbb"}
        mock_lidarr_repo.get_artist_details.side_effect = Exception("Lidarr down")
        artist = _make_artist(in_lidarr=False)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_lidarr is True
        assert artist.monitored is False
        assert artist.auto_download is False

    @pytest.mark.asyncio
    async def test_already_in_lidarr_refreshes_monitoring_flags(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_mbids.return_value = {"aaa-bbb"}
        mock_lidarr_repo.get_artist_details.return_value = {
            "monitored": False, "monitor_new_items": "none",
        }
        artist = _make_artist(in_lidarr=True, monitored=True, auto_download=True)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_lidarr is True
        assert artist.monitored is False
        assert artist.auto_download is False
        mock_lidarr_repo.get_artist_details.assert_awaited_once_with("aaa-bbb")

    @pytest.mark.asyncio
    async def test_removed_from_artist_mbids_preserves_lidarr_flags(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_artist_mbids.return_value = set()
        artist = _make_artist(in_lidarr=True, monitored=True, auto_download=True)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_library is False
        assert artist.in_lidarr is True
        assert artist.monitored is True
        assert artist.auto_download is True

    @pytest.mark.asyncio
    async def test_not_configured_skips(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.is_configured.return_value = False
        artist = _make_artist(in_lidarr=False)

        await artist_service._refresh_library_flags(artist)

        assert artist.in_lidarr is False
        mock_lidarr_repo.get_artist_mbids.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_release_in_library_flags_still_refreshed(self, artist_service, mock_lidarr_repo):
        mock_lidarr_repo.get_library_mbids.return_value = {"album-1"}
        mock_lidarr_repo.get_requested_mbids.return_value = {"album-2"}
        mock_lidarr_repo.get_artist_mbids.return_value = set()

        from models.artist import ReleaseItem
        artist = _make_artist()
        artist = ArtistInfo(
            name="Test", musicbrainz_id="aaa-bbb",
            albums=[
                ReleaseItem(id="album-1", title="A"),
                ReleaseItem(id="album-2", title="B"),
                ReleaseItem(id="album-3", title="C"),
            ],
        )

        await artist_service._refresh_library_flags(artist)

        assert artist.albums[0].in_library is True
        assert artist.albums[0].requested is False
        assert artist.albums[1].in_library is False
        assert artist.albums[1].requested is True
        assert artist.albums[2].in_library is False
        assert artist.albums[2].requested is False

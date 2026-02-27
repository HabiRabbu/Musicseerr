import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.schemas.settings import (
    ListenBrainzConnectionSettings,
    LastFmConnectionSettings,
    PrimaryMusicSourceSettings,
)
from api.v1.schemas.advanced_settings import AdvancedSettings
from repositories.lastfm_models import LastFmArtist, LastFmAlbum
from services.discover_service import DiscoverService


def _make_lb_settings(
    enabled: bool = True, username: str = "lbuser"
) -> ListenBrainzConnectionSettings:
    return ListenBrainzConnectionSettings(
        user_token="tok",
        username=username,
        enabled=enabled,
    )


def _make_lfm_settings(
    enabled: bool = True, username: str = "lfmuser"
) -> LastFmConnectionSettings:
    return LastFmConnectionSettings(
        api_key="key",
        shared_secret="secret",
        session_key="sk",
        username=username,
        enabled=enabled,
    )


def _make_prefs(
    lb_enabled: bool = True,
    lfm_enabled: bool = True,
    primary_source: str = "listenbrainz",
) -> MagicMock:
    prefs = MagicMock()
    prefs.get_listenbrainz_connection.return_value = _make_lb_settings(enabled=lb_enabled)
    prefs.get_lastfm_connection.return_value = _make_lfm_settings(enabled=lfm_enabled)
    prefs.is_lastfm_enabled.return_value = lfm_enabled
    prefs.get_primary_music_source.return_value = PrimaryMusicSourceSettings(source=primary_source)
    prefs.get_advanced_settings.return_value = AdvancedSettings()

    jf_settings = MagicMock()
    jf_settings.enabled = False
    jf_settings.jellyfin_url = ""
    jf_settings.api_key = ""
    jf_settings.user_id = ""
    prefs.get_jellyfin_connection.return_value = jf_settings

    lidarr = MagicMock()
    lidarr.lidarr_url = ""
    lidarr.lidarr_api_key = ""
    prefs.get_lidarr_connection.return_value = lidarr

    yt = MagicMock()
    yt.enabled = False
    yt.api_key = ""
    prefs.get_youtube_connection.return_value = yt

    lf = MagicMock()
    lf.enabled = False
    lf.music_path = ""
    prefs.get_local_files_connection.return_value = lf

    return prefs


def _make_service(
    lb_enabled: bool = True,
    lfm_enabled: bool = True,
    primary_source: str = "listenbrainz",
) -> tuple[DiscoverService, AsyncMock, AsyncMock, MagicMock]:
    lb_repo = AsyncMock()
    lb_repo.get_sitewide_top_artists = AsyncMock(return_value=[])
    lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=[])
    lb_repo.get_user_fresh_releases = AsyncMock(return_value=None)
    lb_repo.get_user_genre_activity = AsyncMock(return_value=None)
    lb_repo.get_user_top_artists = AsyncMock(return_value=[])
    lb_repo.get_similar_artists = AsyncMock(return_value=[])
    lb_repo.get_artist_top_release_groups = AsyncMock(return_value=[])
    lb_repo.configure = MagicMock()

    lfm_repo = AsyncMock()
    lfm_repo.get_global_top_artists = AsyncMock(return_value=[])
    lfm_repo.get_user_weekly_artist_chart = AsyncMock(return_value=[])
    lfm_repo.get_user_top_albums = AsyncMock(return_value=[])
    lfm_repo.get_user_recent_tracks = AsyncMock(return_value=[])
    lfm_repo.get_user_top_artists = AsyncMock(return_value=[])
    lfm_repo.get_similar_artists = AsyncMock(return_value=[])
    lfm_repo.get_artist_top_albums = AsyncMock(return_value=[])

    jf_repo = AsyncMock()
    lidarr_repo = AsyncMock()
    mb_repo = AsyncMock()
    mb_repo.search_release_groups_by_tag = AsyncMock(return_value=[])
    mb_repo.get_release_group_id_from_release = AsyncMock(return_value=None)
    mb_repo.get_release_group_by_id = AsyncMock(return_value=None)

    prefs = _make_prefs(
        lb_enabled=lb_enabled,
        lfm_enabled=lfm_enabled,
        primary_source=primary_source,
    )

    service = DiscoverService(
        listenbrainz_repo=lb_repo,
        jellyfin_repo=jf_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=mb_repo,
        preferences_service=prefs,
        lastfm_repo=lfm_repo,
    )
    return service, lb_repo, lfm_repo, prefs


class TestBuildQueueSourceRouting:
    @pytest.mark.asyncio
    async def test_build_queue_uses_lastfm_when_source_is_lastfm(self):
        """When source=lastfm and Last.fm is enabled, anonymous queue should call Last.fm APIs."""
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        lfm_repo.get_global_top_artists.return_value = [
            LastFmArtist(name="Artist1", mbid="mbid-1", playcount=1000, listeners=500),
        ]
        lfm_repo.get_artist_top_albums.return_value = [
            LastFmAlbum(name="Album1", mbid="album-mbid-1", playcount=100, artist_name="Artist1"),
        ]

        result = await service.build_queue(count=5, source="lastfm")
        assert result is not None
        lfm_repo.get_global_top_artists.assert_awaited()
        lb_repo.get_sitewide_top_release_groups.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_build_queue_uses_listenbrainz_when_source_is_lb(self):
        """When source=listenbrainz, anonymous queue should call LB APIs."""
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="listenbrainz"
        )
        lb_repo.get_sitewide_top_release_groups.return_value = []

        result = await service.build_queue(count=5, source="listenbrainz")
        assert result is not None
        lb_repo.get_sitewide_top_release_groups.assert_awaited()
        lfm_repo.get_global_top_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_build_queue_none_source_uses_global_default(self):
        """When source=None, queue should use the global primary source."""
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        lfm_repo.get_global_top_artists.return_value = []

        result = await service.build_queue(count=5, source=None)
        assert result is not None
        lfm_repo.get_global_top_artists.assert_awaited()

    @pytest.mark.asyncio
    async def test_build_queue_returns_valid_response(self):
        """build_queue should return a DiscoverQueueResponse with queue_id."""
        service, _, _, _ = _make_service(lb_enabled=False, lfm_enabled=False)
        result = await service.build_queue(count=5)
        assert result is not None
        assert result.queue_id
        assert isinstance(result.items, list)


class TestBuildQueuePersonalizedSourceRouting:
    @pytest.mark.asyncio
    async def test_personalized_queue_lastfm_uses_lastfm_similar(self):
        """Personalized queue with lastfm source should call Last.fm similar artists."""
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="lastfm"
        )
        lfm_repo.get_user_top_artists.return_value = [
            LastFmArtist(name="Seed", mbid="seed-mbid", playcount=500, listeners=100),
        ]
        lfm_repo.get_similar_artists.return_value = []

        await service.build_queue(count=5, source="lastfm")
        lfm_repo.get_user_top_artists.assert_awaited()
        lfm_repo.get_similar_artists.assert_awaited()
        lb_repo.get_similar_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_personalized_queue_lb_uses_lb_similar(self):
        """Personalized queue with listenbrainz source should call LB similar artists."""
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="listenbrainz"
        )
        lb_repo.get_user_top_artists.return_value = [
            MagicMock(artist_name="Seed", artist_mbids=["seed-mbid"], listen_count=500),
        ]
        lb_repo.get_similar_artists.return_value = []

        await service.build_queue(count=5, source="listenbrainz")
        lb_repo.get_user_top_artists.assert_awaited()
        lb_repo.get_similar_artists.assert_awaited()
        lfm_repo.get_similar_artists.assert_not_awaited()


class TestLastFmQueueDataQuality:
    @pytest.mark.asyncio
    async def test_lastfm_queue_normalizes_release_mbids_to_release_groups(self):
        service, _, lfm_repo, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        service._mb_repo.get_release_group_id_from_release.return_value = "rg-mbid-1"

        lfm_repo.get_global_top_artists.return_value = [
            LastFmArtist(name="Artist1", mbid="artist-mbid-1", playcount=1000, listeners=500),
        ]
        lfm_repo.get_artist_top_albums.return_value = [
            LastFmAlbum(name="Album1", mbid="release-mbid-1", playcount=100, artist_name="Artist1"),
        ]

        result = await service.build_queue(count=5, source="lastfm")

        assert any(item.release_group_mbid == "rg-mbid-1" for item in result.items)
        service._mb_repo.get_release_group_id_from_release.assert_awaited()

    @pytest.mark.asyncio
    async def test_lastfm_seed_collection_does_not_call_listenbrainz_fallback(self):
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="lastfm"
        )
        lfm_repo.get_user_top_artists.return_value = []
        lfm_repo.get_global_top_artists.return_value = []

        await service.build_queue(count=5, source="lastfm")

        lb_repo.get_user_top_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lastfm_queue_keeps_items_when_release_group_resolution_fails(self):
        service, _, lfm_repo, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        service._mb_repo.get_release_group_id_from_release.return_value = None
        service._mb_repo.get_release_group_by_id.return_value = None

        lfm_repo.get_global_top_artists.return_value = [
            LastFmArtist(name="Artist1", mbid="artist-mbid-1", playcount=1000, listeners=500),
        ]
        lfm_repo.get_artist_top_albums.return_value = [
            LastFmAlbum(name="Album1", mbid="release-mbid-1", playcount=100, artist_name="Artist1"),
        ]

        result = await service.build_queue(count=5, source="lastfm")

        assert result.items
        assert any(item.release_group_mbid == "release-mbid-1" for item in result.items)

    @pytest.mark.asyncio
    async def test_lastfm_queue_items_are_deduplicated_by_release_group_mbid(self):
        service, _, _, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )

        service._resolve_lastfm_release_group_mbids = AsyncMock(return_value={
            "release-a": "rg-shared",
            "release-b": "rg-shared",
        })

        artist_a = LastFmArtist(name="Artist A", mbid="artist-a", playcount=100, listeners=10)
        artist_b = LastFmArtist(name="Artist B", mbid="artist-b", playcount=120, listeners=12)
        albums_a = [LastFmAlbum(name="Album A", mbid="release-a", playcount=50, artist_name="Artist A")]
        albums_b = [LastFmAlbum(name="Album B", mbid="release-b", playcount=60, artist_name="Artist B")]

        items = await service._lastfm_albums_to_queue_items(
            [(artist_a, albums_a), (artist_b, albums_b)],
            exclude=set(),
            target=5,
            reason="Trending on Last.fm",
        )

        assert len(items) == 1
        assert items[0].release_group_mbid == "rg-shared"


class TestLastFmResolutionBehavior:
    @pytest.mark.asyncio
    async def test_lastfm_resolution_caps_musicbrainz_lookup_count(self):
        service, _, _, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )

        album_mbids = [f"release-mbid-{idx}" for idx in range(10)]

        await service._resolve_lastfm_release_group_mbids(album_mbids, max_lookups=3)

        assert service._mb_repo.get_release_group_id_from_release.await_count == 3


class TestLastFmQueueResilience:
    @pytest.mark.asyncio
    async def test_lastfm_queue_falls_back_to_decade_results_when_top_albums_sparse(self):
        service, _, lfm_repo, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )

        lfm_repo.get_user_top_artists.return_value = []
        lfm_repo.get_global_top_artists.return_value = [
            LastFmArtist(name="Artist1", mbid="artist-mbid-1", playcount=1000, listeners=500),
        ]
        lfm_repo.get_artist_top_albums.return_value = [
            LastFmAlbum(name="Album No MBID", mbid=None, playcount=100, artist_name="Artist1"),
        ]

        fallback_rg = MagicMock()
        fallback_rg.musicbrainz_id = "rg-fallback-1"
        fallback_rg.title = "Fallback Album"
        fallback_rg.artist = "Fallback Artist"

        async def _search_release_groups_by_tag(tag, limit=25, offset=0):
            if tag == "1990s" and offset == 0:
                return [fallback_rg]
            return []

        service._mb_repo.search_release_groups_by_tag = AsyncMock(
            side_effect=_search_release_groups_by_tag
        )

        result = await service.build_queue(count=5, source="lastfm")

        assert result.items
        assert any(item.release_group_mbid == "rg-fallback-1" for item in result.items)

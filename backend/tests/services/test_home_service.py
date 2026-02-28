import pytest
from unittest.mock import AsyncMock, MagicMock

from api.v1.schemas.settings import (
    ListenBrainzConnectionSettings,
    LastFmConnectionSettings,
    PrimaryMusicSourceSettings,
)
from api.v1.schemas.library import LibraryAlbum
from repositories.protocols import ListenBrainzReleaseGroup
from services.home_service import HomeService


def _make_prefs(
    lb_enabled: bool = True,
    lfm_enabled: bool = True,
    primary_source: str = "listenbrainz",
) -> MagicMock:
    prefs = MagicMock()
    lb_settings = ListenBrainzConnectionSettings(
        user_token="tok", username="lbuser", enabled=lb_enabled
    )
    prefs.get_listenbrainz_connection.return_value = lb_settings

    lfm_settings = LastFmConnectionSettings(
        api_key="key",
        shared_secret="secret",
        session_key="sk",
        username="lfmuser",
        enabled=lfm_enabled,
    )
    prefs.get_lastfm_connection.return_value = lfm_settings
    prefs.is_lastfm_enabled.return_value = lfm_enabled
    prefs.get_primary_music_source.return_value = PrimaryMusicSourceSettings(source=primary_source)

    jf_settings = MagicMock()
    jf_settings.enabled = False
    jf_settings.jellyfin_url = ""
    jf_settings.api_key = ""
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
) -> tuple[HomeService, AsyncMock, AsyncMock, MagicMock]:
    lb_repo = AsyncMock()
    lb_repo.get_sitewide_top_artists = AsyncMock(return_value=[])
    lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=[])
    lb_repo.get_user_listens = AsyncMock(return_value=[])
    lb_repo.get_user_loved_recordings = AsyncMock(return_value=[])
    lb_repo.get_user_genre_activity = AsyncMock(return_value=None)
    lb_repo.configure = MagicMock()

    lfm_repo = AsyncMock()
    lfm_repo.get_global_top_artists = AsyncMock(return_value=[])
    lfm_repo.get_user_top_albums = AsyncMock(return_value=[])
    lfm_repo.get_user_recent_tracks = AsyncMock(return_value=[])
    lfm_repo.get_user_loved_tracks = AsyncMock(return_value=[])

    jf_repo = AsyncMock()
    lidarr_repo = AsyncMock()
    lidarr_repo.get_library = AsyncMock(return_value=[])
    lidarr_repo.get_artists_from_library = AsyncMock(return_value=[])
    lidarr_repo.get_recently_imported = AsyncMock(return_value=[])
    mb_repo = AsyncMock()

    prefs = _make_prefs(
        lb_enabled=lb_enabled,
        lfm_enabled=lfm_enabled,
        primary_source=primary_source,
    )

    service = HomeService(
        listenbrainz_repo=lb_repo,
        jellyfin_repo=jf_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=mb_repo,
        preferences_service=prefs,
        lastfm_repo=lfm_repo,
    )
    return service, lb_repo, lfm_repo, prefs


class TestHomeServiceResolveSource:
    def test_explicit_source_overrides_global(self):
        service, _, _, _ = _make_service(primary_source="lastfm")
        assert service._resolve_source("listenbrainz") == "listenbrainz"

    def test_none_uses_global_setting(self):
        service, _, _, _ = _make_service(primary_source="lastfm")
        assert service._resolve_source(None) == "lastfm"


class TestHomeServiceSourceSelection:
    @pytest.mark.asyncio
    async def test_lb_trending_called_when_source_is_lb(self):
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="listenbrainz"
        )
        await service.get_home_data("listenbrainz")
        lb_repo.get_sitewide_top_artists.assert_awaited_once()
        lfm_repo.get_global_top_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lfm_trending_called_when_source_is_lastfm(self):
        service, lb_repo, lfm_repo, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="lastfm"
        )
        await service.get_home_data("lastfm")
        lfm_repo.get_global_top_artists.assert_awaited_once()
        lb_repo.get_sitewide_top_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_source_field_in_response(self):
        service, _, _, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="listenbrainz"
        )
        response = await service.get_home_data("listenbrainz")
        assert response.integration_status is not None
        assert response.integration_status.lastfm is True
        assert response.integration_status.listenbrainz is True

    @pytest.mark.asyncio
    async def test_popular_album_in_library_uses_album_mbids_not_artist_mbids(self):
        service, lb_repo, _, prefs = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="listenbrainz"
        )
        lidarr_conn = MagicMock()
        lidarr_conn.lidarr_url = "http://lidarr.local"
        lidarr_conn.lidarr_api_key = "apikey"
        prefs.get_lidarr_connection.return_value = lidarr_conn
        service._lidarr_repo.get_library.return_value = [
            LibraryAlbum(
                artist="Artist",
                album="Album",
                monitored=True,
                musicbrainz_id="rg-123",
                artist_mbid="artist-123",
            )
        ]
        service._lidarr_repo.get_artists_from_library.return_value = [{"mbid": "artist-123"}]
        lb_repo.get_sitewide_top_release_groups.return_value = [
            ListenBrainzReleaseGroup(
                release_group_name="Album",
                artist_name="Artist",
                listen_count=99,
                release_group_mbid="rg-123",
                artist_mbids=["artist-other"],
            )
        ]

        response = await service.get_home_data("listenbrainz")

        assert response.popular_albums is not None
        assert len(response.popular_albums.items) == 1
        assert response.popular_albums.items[0].in_library is True

    @pytest.mark.asyncio
    async def test_lastfm_source_skips_user_top_albums_when_username_missing(self):
        service, _, lfm_repo, prefs = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        prefs.get_lastfm_connection.return_value = LastFmConnectionSettings(
            api_key="key",
            shared_secret="secret",
            session_key="sk",
            username="",
            enabled=True,
        )

        await service.get_home_data("lastfm")

        lfm_repo.get_global_top_artists.assert_awaited_once()
        lfm_repo.get_user_top_albums.assert_not_awaited()


class TestHomeServiceCacheKeySourceAware:
    def test_different_sources_produce_different_keys(self):
        service, _, _, _ = _make_service()
        key_lb = service._get_home_cache_key("listenbrainz")
        key_lfm = service._get_home_cache_key("lastfm")
        assert key_lb != key_lfm


class TestBuildServicePrompts:
    def test_source_prompts_hidden_when_one_source_enabled(self):
        service, _, _, _ = _make_service()
        prompts = service._build_service_prompts(
            lb_enabled=True, lidarr_configured=True, lfm_enabled=False
        )
        services = [p.service for p in prompts]
        assert "lastfm" not in services
        assert "listenbrainz" not in services

    def test_source_prompts_hidden_when_lastfm_enabled(self):
        service, _, _, _ = _make_service()
        prompts = service._build_service_prompts(
            lb_enabled=False, lidarr_configured=True, lfm_enabled=True
        )
        services = [p.service for p in prompts]
        assert "listenbrainz" not in services
        assert "lastfm" not in services

    def test_no_prompts_when_all_enabled(self):
        service, _, _, _ = _make_service()
        prompts = service._build_service_prompts(
            lb_enabled=True, lidarr_configured=True, lfm_enabled=True
        )
        assert prompts == []

    def test_all_prompts_when_nothing_enabled(self):
        service, _, _, _ = _make_service()
        prompts = service._build_service_prompts(
            lb_enabled=False, lidarr_configured=False, lfm_enabled=False
        )
        services = {p.service for p in prompts}
        assert services == {"lidarr-connection", "listenbrainz", "lastfm"}

    def test_lb_prompt_mentions_lastfm(self):
        service, _, _, _ = _make_service()
        prompts = service._build_service_prompts(
            lb_enabled=False, lidarr_configured=True, lfm_enabled=False
        )
        lb_prompt = next(p for p in prompts if p.service == "listenbrainz")
        assert "last.fm" in lb_prompt.description.lower()

import pytest
from unittest.mock import AsyncMock, MagicMock

from api.v1.schemas.search import (
    ArtistEnrichmentRequest,
    AlbumEnrichmentRequest,
    EnrichmentBatchRequest,
)
from api.v1.schemas.settings import (
    ListenBrainzConnectionSettings,
    LastFmConnectionSettings,
    PrimaryMusicSourceSettings,
)
from services.search_enrichment_service import SearchEnrichmentService


def _make_prefs(
    lb_enabled: bool = True,
    lfm_enabled: bool = False,
    primary_source: str = "listenbrainz",
) -> MagicMock:
    prefs = MagicMock()
    lb_settings = ListenBrainzConnectionSettings(
        user_token="tok", username="lbuser", enabled=lb_enabled
    )
    prefs.get_listenbrainz_connection.return_value = lb_settings

    lfm_settings = LastFmConnectionSettings(
        api_key="key" if lfm_enabled else "",
        shared_secret="secret",
        session_key="sk",
        username="lfmuser",
        enabled=lfm_enabled,
    )
    prefs.get_lastfm_connection.return_value = lfm_settings
    prefs.get_primary_music_source.return_value = PrimaryMusicSourceSettings(
        source=primary_source
    )
    return prefs


def _make_service(
    lb_enabled: bool = True,
    lfm_enabled: bool = False,
    primary_source: str = "listenbrainz",
) -> tuple[SearchEnrichmentService, AsyncMock, AsyncMock, AsyncMock]:
    mb_repo = AsyncMock()
    mb_repo.get_artist_release_groups = AsyncMock(return_value=([], 5))

    lb_repo = AsyncMock()
    lb_repo.get_artist_top_release_groups = AsyncMock(return_value=[])
    lb_repo.get_release_group_popularity_batch = AsyncMock(return_value={})

    lfm_repo = AsyncMock()
    lfm_repo.get_artist_info = AsyncMock(return_value=None)
    lfm_repo.get_album_info = AsyncMock(return_value=None)

    prefs = _make_prefs(
        lb_enabled=lb_enabled, lfm_enabled=lfm_enabled, primary_source=primary_source
    )

    service = SearchEnrichmentService(
        mb_repo=mb_repo,
        lb_repo=lb_repo,
        preferences_service=prefs,
        lastfm_repo=lfm_repo,
    )
    return service, mb_repo, lb_repo, lfm_repo


class TestSourceSelection:
    def test_source_listenbrainz_when_lb_enabled(self):
        service, _, _, _ = _make_service(lb_enabled=True, lfm_enabled=False)
        assert service._get_enrichment_source() == "listenbrainz"

    def test_source_lastfm_when_lfm_preferred(self):
        service, _, _, _ = _make_service(
            lb_enabled=True, lfm_enabled=True, primary_source="lastfm"
        )
        assert service._get_enrichment_source() == "lastfm"

    def test_source_none_when_nothing_enabled(self):
        service, _, _, _ = _make_service(lb_enabled=False, lfm_enabled=False)
        assert service._get_enrichment_source() == "none"

    def test_fallback_lb_when_lastfm_preferred_but_disabled(self):
        service, _, _, _ = _make_service(
            lb_enabled=True, lfm_enabled=False, primary_source="lastfm"
        )
        assert service._get_enrichment_source() == "listenbrainz"

    def test_fallback_lastfm_when_lb_preferred_but_disabled(self):
        service, _, _, _ = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="listenbrainz"
        )
        assert service._get_enrichment_source() == "lastfm"


class TestEnrichBatch:
    @pytest.mark.asyncio
    async def test_listenbrainz_enrichment_path(self):
        service, mb_repo, lb_repo, lfm_repo = _make_service(
            lb_enabled=True, lfm_enabled=False
        )
        lb_repo.get_release_group_popularity_batch.return_value = {"album-1": 1000}

        request = EnrichmentBatchRequest(
            artists=[ArtistEnrichmentRequest(musicbrainz_id="art-1", name="Muse")],
            albums=[
                AlbumEnrichmentRequest(
                    musicbrainz_id="album-1", artist_name="Muse", album_name="Absolution"
                )
            ],
        )
        result = await service.enrich_batch(request)

        assert result.source == "listenbrainz"
        assert len(result.artists) == 1
        assert result.artists[0].release_group_count == 5
        assert len(result.albums) == 1
        assert result.albums[0].listen_count == 1000
        lb_repo.get_release_group_popularity_batch.assert_awaited_once()
        lfm_repo.get_album_info.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lastfm_enrichment_path(self):
        service, mb_repo, lb_repo, lfm_repo = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )

        artist_info = MagicMock()
        artist_info.listeners = 500000
        lfm_repo.get_artist_info.return_value = artist_info

        album_info = MagicMock()
        album_info.playcount = 1200000
        lfm_repo.get_album_info.return_value = album_info

        request = EnrichmentBatchRequest(
            artists=[ArtistEnrichmentRequest(musicbrainz_id="art-1", name="Muse")],
            albums=[
                AlbumEnrichmentRequest(
                    musicbrainz_id="album-1", artist_name="Muse", album_name="Absolution"
                )
            ],
        )
        result = await service.enrich_batch(request)

        assert result.source == "lastfm"
        assert result.artists[0].listen_count == 500000
        assert result.albums[0].listen_count == 1200000
        lb_repo.get_release_group_popularity_batch.assert_not_awaited()
        lfm_repo.get_artist_info.assert_awaited_once()
        lfm_repo.get_album_info.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lastfm_zero_artist_listeners_preserved(self):
        service, _, _, lfm_repo = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        artist_info = MagicMock()
        artist_info.listeners = 0
        lfm_repo.get_artist_info.return_value = artist_info

        request = EnrichmentBatchRequest(
            artists=[ArtistEnrichmentRequest(musicbrainz_id="art-1", name="Obscure")],
            albums=[],
        )
        result = await service.enrich_batch(request)

        assert result.artists[0].listen_count == 0

    @pytest.mark.asyncio
    async def test_lastfm_zero_album_playcount_preserved(self):
        service, _, _, lfm_repo = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )
        album_info = MagicMock()
        album_info.playcount = 0
        lfm_repo.get_album_info.return_value = album_info

        request = EnrichmentBatchRequest(
            artists=[],
            albums=[
                AlbumEnrichmentRequest(
                    musicbrainz_id="album-1", artist_name="Obscure", album_name="Debut"
                )
            ],
        )
        result = await service.enrich_batch(request)

        assert result.albums[0].listen_count == 0

    @pytest.mark.asyncio
    async def test_none_source_returns_release_counts_only(self):
        service, mb_repo, lb_repo, lfm_repo = _make_service(
            lb_enabled=False, lfm_enabled=False
        )

        request = EnrichmentBatchRequest(
            artists=[ArtistEnrichmentRequest(musicbrainz_id="art-1", name="Muse")],
            albums=[
                AlbumEnrichmentRequest(
                    musicbrainz_id="album-1", artist_name="Muse", album_name="Absolution"
                )
            ],
        )
        result = await service.enrich_batch(request)

        assert result.source == "none"
        assert result.artists[0].release_group_count == 5
        assert result.artists[0].listen_count is None
        assert result.albums[0].listen_count is None

    @pytest.mark.asyncio
    async def test_lastfm_artist_enrichment_without_name_skips_lfm(self):
        service, _, lb_repo, lfm_repo = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )

        request = EnrichmentBatchRequest(
            artists=[ArtistEnrichmentRequest(musicbrainz_id="art-1", name="")],
            albums=[],
        )
        result = await service.enrich_batch(request)

        assert result.source == "lastfm"
        assert result.artists[0].listen_count is None
        lfm_repo.get_artist_info.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lastfm_album_without_names_skips_lfm(self):
        service, _, _, lfm_repo = _make_service(
            lb_enabled=False, lfm_enabled=True, primary_source="lastfm"
        )

        request = EnrichmentBatchRequest(
            artists=[],
            albums=[
                AlbumEnrichmentRequest(
                    musicbrainz_id="album-1", artist_name="", album_name=""
                )
            ],
        )
        result = await service.enrich_batch(request)

        assert result.albums[0].listen_count is None
        lfm_repo.get_album_info.assert_not_awaited()


class TestLegacyEnrich:
    @pytest.mark.asyncio
    async def test_legacy_enrich_still_works(self):
        service, _, lb_repo, _ = _make_service(lb_enabled=True, lfm_enabled=False)
        lb_repo.get_release_group_popularity_batch.return_value = {"album-1": 42}

        result = await service.enrich(
            artist_mbids=["art-1"],
            album_mbids=["album-1"],
        )

        assert result.source == "listenbrainz"
        assert len(result.artists) == 1
        assert len(result.albums) == 1
        assert result.albums[0].listen_count == 42

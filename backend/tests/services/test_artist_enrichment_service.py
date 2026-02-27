import pytest
from unittest.mock import AsyncMock, MagicMock

from repositories.lastfm_models import LastFmArtistInfo, LastFmTag, LastFmSimilarArtist
from services.artist_enrichment_service import ArtistEnrichmentService


def _make_lastfm_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_artist_info = AsyncMock(
        return_value=LastFmArtistInfo(
            name="Radiohead",
            mbid="a74b1b7f-71a5-4011-9441-d0b5e4122711",
            listeners=5_000_000,
            playcount=300_000_000,
            url="https://www.last.fm/music/Radiohead",
            bio_summary="Radiohead are an English <b>rock</b> band from <a href='#'>Abingdon</a>.",
            tags=[
                LastFmTag(name="alternative", url="https://last.fm/tag/alternative"),
                LastFmTag(name="rock", url="https://last.fm/tag/rock"),
            ],
            similar=[
                LastFmSimilarArtist(
                    name="Thom Yorke", mbid="abc-123", match=0.95, url="https://last.fm/thom"
                ),
            ],
        )
    )
    return repo


def _make_preferences(enabled: bool = True) -> MagicMock:
    prefs = MagicMock()
    prefs.is_lastfm_enabled.return_value = enabled
    return prefs


@pytest.mark.asyncio
async def test_enrichment_returns_data_when_enabled():
    repo = _make_lastfm_repo()
    prefs = _make_preferences(enabled=True)
    svc = ArtistEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("a74b1b7f", "Radiohead")

    assert result is not None
    assert result.listeners == 5_000_000
    assert result.playcount == 300_000_000
    assert result.url == "https://www.last.fm/music/Radiohead"
    assert len(result.tags) == 2
    assert result.tags[0].name == "alternative"
    assert len(result.similar_artists) == 1
    assert result.similar_artists[0].name == "Thom Yorke"


@pytest.mark.asyncio
async def test_enrichment_strips_html_from_bio():
    repo = _make_lastfm_repo()
    prefs = _make_preferences(enabled=True)
    svc = ArtistEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("a74b1b7f", "Radiohead")

    assert result is not None
    assert "<b>" not in (result.bio or "")
    assert "<a" not in (result.bio or "")
    assert "Radiohead are an English rock band from Abingdon." in (result.bio or "")


@pytest.mark.asyncio
async def test_enrichment_returns_none_when_disabled():
    repo = _make_lastfm_repo()
    prefs = _make_preferences(enabled=False)
    svc = ArtistEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("a74b1b7f", "Radiohead")

    assert result is None
    repo.get_artist_info.assert_not_called()


@pytest.mark.asyncio
async def test_enrichment_returns_none_when_api_returns_none():
    repo = AsyncMock()
    repo.get_artist_info = AsyncMock(return_value=None)
    prefs = _make_preferences(enabled=True)
    svc = ArtistEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("a74b1b7f", "Radiohead")

    assert result is None


@pytest.mark.asyncio
async def test_enrichment_returns_none_on_exception():
    repo = AsyncMock()
    repo.get_artist_info = AsyncMock(side_effect=Exception("API error"))
    prefs = _make_preferences(enabled=True)
    svc = ArtistEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("a74b1b7f", "Radiohead")

    assert result is None

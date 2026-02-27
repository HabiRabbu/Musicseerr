import pytest
from unittest.mock import AsyncMock, MagicMock

from repositories.lastfm_models import LastFmAlbumInfo, LastFmTag
from services.album_enrichment_service import AlbumEnrichmentService


def _make_lastfm_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_album_info = AsyncMock(
        return_value=LastFmAlbumInfo(
            name="OK Computer",
            artist_name="Radiohead",
            mbid="album-mbid-123",
            listeners=2_000_000,
            playcount=100_000_000,
            url="https://www.last.fm/music/Radiohead/OK+Computer",
            summary="OK Computer is the third <b>studio album</b> by Radiohead.",
            tags=[
                LastFmTag(name="alternative rock", url="https://last.fm/tag/alternative+rock"),
                LastFmTag(name="90s", url="https://last.fm/tag/90s"),
            ],
        )
    )
    return repo


def _make_preferences(enabled: bool = True) -> MagicMock:
    prefs = MagicMock()
    prefs.is_lastfm_enabled.return_value = enabled
    return prefs


@pytest.mark.asyncio
async def test_album_enrichment_returns_data_when_enabled():
    repo = _make_lastfm_repo()
    prefs = _make_preferences(enabled=True)
    svc = AlbumEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("Radiohead", "OK Computer", "album-mbid-123")

    assert result is not None
    assert result.listeners == 2_000_000
    assert result.playcount == 100_000_000
    assert result.url == "https://www.last.fm/music/Radiohead/OK+Computer"
    assert len(result.tags) == 2
    assert result.tags[0].name == "alternative rock"


@pytest.mark.asyncio
async def test_album_enrichment_strips_html_from_summary():
    repo = _make_lastfm_repo()
    prefs = _make_preferences(enabled=True)
    svc = AlbumEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("Radiohead", "OK Computer")

    assert result is not None
    assert "<b>" not in (result.summary or "")
    assert "OK Computer is the third studio album by Radiohead." in (result.summary or "")


@pytest.mark.asyncio
async def test_album_enrichment_returns_none_when_disabled():
    repo = _make_lastfm_repo()
    prefs = _make_preferences(enabled=False)
    svc = AlbumEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("Radiohead", "OK Computer")

    assert result is None
    repo.get_album_info.assert_not_called()


@pytest.mark.asyncio
async def test_album_enrichment_returns_none_when_api_returns_none():
    repo = AsyncMock()
    repo.get_album_info = AsyncMock(return_value=None)
    prefs = _make_preferences(enabled=True)
    svc = AlbumEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("Radiohead", "OK Computer")

    assert result is None


@pytest.mark.asyncio
async def test_album_enrichment_returns_none_on_exception():
    repo = AsyncMock()
    repo.get_album_info = AsyncMock(side_effect=Exception("API error"))
    prefs = _make_preferences(enabled=True)
    svc = AlbumEnrichmentService(lastfm_repo=repo, preferences_service=prefs)

    result = await svc.get_lastfm_enrichment("Radiohead", "OK Computer")

    assert result is None

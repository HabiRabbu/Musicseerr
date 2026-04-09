from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from api.v1.schemas.plex import (
    PlexAlbumDetail,
    PlexAlbumMatch,
    PlexAlbumSummary,
    PlexArtistSummary,
    PlexLibraryStats,
    PlexSearchResponse,
    PlexTrackInfo,
)
from repositories.plex_models import PlexAlbum, PlexArtist, PlexTrack
from services.plex_library_service import PlexLibraryService


def _make_plex_conn(enabled: bool = True, url: str = "http://plex:32400", token: str = "tok", library_ids: list[str] | None = None):
    conn = MagicMock()
    conn.enabled = enabled
    conn.plex_url = url
    conn.plex_token = token
    conn.music_library_ids = library_ids or ["1"]
    return conn


def _make_service(
    configured: bool = True,
    section_ids: list[str] | None = None,
) -> tuple[PlexLibraryService, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.get_albums = AsyncMock(return_value=([], 0))
    repo.get_artists = AsyncMock(return_value=[])
    repo.get_album_metadata = AsyncMock()
    repo.get_album_tracks = AsyncMock(return_value=[])
    repo.get_recently_added = AsyncMock(return_value=[])
    repo.get_recently_viewed = AsyncMock(return_value=[])
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_track_count = AsyncMock(return_value=0)
    repo.get_artist_count = AsyncMock(return_value=0)
    repo.search = AsyncMock(return_value={"albums": [], "tracks": [], "artists": []})
    type(repo).stats_ttl = PropertyMock(return_value=600)

    prefs = MagicMock()
    ids = section_ids if section_ids is not None else (["1"] if configured else [])
    prefs.get_plex_connection_raw.return_value = _make_plex_conn(
        enabled=configured, library_ids=ids,
    )

    service = PlexLibraryService(
        plex_repo=repo,
        preferences_service=prefs,
    )
    return service, repo, prefs


def _album(key: str = "100", title: str = "Album", parent: str = "Artist") -> PlexAlbum:
    return PlexAlbum(
        ratingKey=key,
        title=title,
        parentTitle=parent,
        leafCount=10,
        year=2024,
    )


def _artist(key: str = "50", title: str = "Artist") -> PlexArtist:
    return PlexArtist(ratingKey=key, title=title)


def _track(key: str = "200", title: str = "Track 1") -> PlexTrack:
    return PlexTrack(
        ratingKey=key,
        title=title,
        index=1,
        duration=180000,
    )


class TestGetAlbums:
    @pytest.mark.asyncio
    async def test_returns_albums_and_total(self):
        service, repo, _ = _make_service()
        repo.get_albums = AsyncMock(return_value=([_album()], 42))
        items, total = await service.get_albums(size=50, offset=0)
        assert len(items) == 1
        assert total == 42
        assert isinstance(items[0], PlexAlbumSummary)

    @pytest.mark.asyncio
    async def test_empty_when_no_sections(self):
        service, _, _ = _make_service(configured=False)
        items, total = await service.get_albums()
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_deduplicates_across_sections(self):
        service, repo, _ = _make_service(section_ids=["1", "2"])
        album = _album(key="100")
        repo.get_albums = AsyncMock(return_value=([album], 1))
        items, total = await service.get_albums()
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_filters_unknown_titles(self):
        service, repo, _ = _make_service()
        albums = [_album(key="1", title="Unknown"), _album(key="2", title="Real Album")]
        repo.get_albums = AsyncMock(return_value=(albums, 2))
        items, _ = await service.get_albums()
        assert all(i.name != "Unknown" for i in items)


class TestGetAlbumDetail:
    @pytest.mark.asyncio
    async def test_found(self):
        service, repo, _ = _make_service()
        repo.get_album_metadata = AsyncMock(return_value=_album())
        repo.get_album_tracks = AsyncMock(return_value=[_track()])
        detail = await service.get_album_detail("100")
        assert detail is not None
        assert isinstance(detail, PlexAlbumDetail)
        assert detail.plex_id == "100"
        assert len(detail.tracks) == 1

    @pytest.mark.asyncio
    async def test_not_found(self):
        service, repo, _ = _make_service()
        repo.get_album_metadata = AsyncMock(side_effect=Exception("not found"))
        detail = await service.get_album_detail("missing")
        assert detail is None


class TestGetArtists:
    @pytest.mark.asyncio
    async def test_returns_artists(self):
        service, repo, _ = _make_service()
        repo.get_artists = AsyncMock(return_value=[_artist()])
        result = await service.get_artists()
        assert len(result) == 1
        assert isinstance(result[0], PlexArtistSummary)

    @pytest.mark.asyncio
    async def test_empty_when_no_sections(self):
        service, _, _ = _make_service(configured=False)
        result = await service.get_artists()
        assert result == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_search_results(self):
        service, repo, _ = _make_service()
        repo.search = AsyncMock(return_value={
            "albums": [_album()],
            "tracks": [_track()],
            "artists": [_artist()],
        })
        result = await service.search("test")
        assert isinstance(result, PlexSearchResponse)
        assert len(result.albums) == 1
        assert len(result.tracks) == 1
        assert len(result.artists) == 1

    @pytest.mark.asyncio
    async def test_empty_when_no_sections(self):
        service, _, _ = _make_service(configured=False)
        result = await service.search("test")
        assert result.albums == []
        assert result.artists == []
        assert result.tracks == []

    @pytest.mark.asyncio
    async def test_deduplicates_across_sections(self):
        service, repo, _ = _make_service(section_ids=["1", "2"])
        repo.search = AsyncMock(return_value={
            "albums": [_album(key="100")],
            "tracks": [],
            "artists": [],
        })
        result = await service.search("test")
        assert len(result.albums) == 1


class TestGetRecent:
    @pytest.mark.asyncio
    async def test_returns_recently_viewed_when_available(self):
        service, repo, _ = _make_service()
        viewed_album = _album(key="200", title="Viewed Album")
        viewed_album.lastViewedAt = 9999
        repo.get_recently_viewed = AsyncMock(return_value=[viewed_album])
        repo.get_recently_added = AsyncMock(return_value=[_album()])
        result = await service.get_recent(limit=20)
        assert len(result) == 1
        assert result[0].name == "Viewed Album"
        repo.get_recently_added.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_recently_added_when_viewed_empty(self):
        service, repo, _ = _make_service()
        repo.get_recently_viewed = AsyncMock(return_value=[])
        repo.get_recently_added = AsyncMock(return_value=[_album()])
        result = await service.get_recent(limit=20)
        assert len(result) == 1
        repo.get_recently_added.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_when_no_sections(self):
        service, _, _ = _make_service(configured=False)
        result = await service.get_recent()
        assert result == []


class TestGetGenres:
    @pytest.mark.asyncio
    async def test_returns_sorted_genres(self):
        service, repo, _ = _make_service()
        repo.get_genres = AsyncMock(return_value=["Rock", "Jazz", "Blues"])
        result = await service.get_genres()
        assert result == ["Blues", "Jazz", "Rock"]

    @pytest.mark.asyncio
    async def test_deduplicates_across_sections(self):
        service, repo, _ = _make_service(section_ids=["1", "2"])
        call_count = 0

        async def side_effect(section_id: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ["Rock", "Jazz"]
            return ["Jazz", "Pop"]

        repo.get_genres = AsyncMock(side_effect=side_effect)
        result = await service.get_genres()
        assert result == ["Jazz", "Pop", "Rock"]

    @pytest.mark.asyncio
    async def test_empty_when_no_sections(self):
        service, _, _ = _make_service(configured=False)
        result = await service.get_genres()
        assert result == []


class TestGetStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self):
        service, repo, _ = _make_service()
        repo.get_albums = AsyncMock(return_value=([], 10))
        repo.get_track_count = AsyncMock(return_value=100)
        repo.get_artist_count = AsyncMock(return_value=5)
        stats = await service.get_stats()
        assert isinstance(stats, PlexLibraryStats)
        assert stats.total_albums == 10
        assert stats.total_tracks == 100
        assert stats.total_artists == 5

    @pytest.mark.asyncio
    async def test_caching(self):
        service, repo, _ = _make_service()
        repo.get_albums = AsyncMock(return_value=([], 5))
        repo.get_track_count = AsyncMock(return_value=50)
        repo.get_artist_count = AsyncMock(return_value=3)

        stats1 = await service.get_stats()
        repo.get_albums.reset_mock()
        repo.get_track_count.reset_mock()
        repo.get_artist_count.reset_mock()

        stats2 = await service.get_stats()
        assert stats1 == stats2
        repo.get_albums.assert_not_awaited()
        repo.get_track_count.assert_not_awaited()
        repo.get_artist_count.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_expiry(self):
        service, repo, _ = _make_service()
        repo.get_albums = AsyncMock(return_value=([], 5))
        repo.get_track_count = AsyncMock(return_value=50)
        repo.get_artist_count = AsyncMock(return_value=3)

        await service.get_stats()

        repo.get_albums.reset_mock()
        repo.get_track_count.reset_mock()
        repo.get_artist_count.reset_mock()

        service._stats_cache_ts -= 700
        await service.get_stats()
        repo.get_albums.assert_awaited()

    @pytest.mark.asyncio
    async def test_empty_when_no_sections(self):
        service, _, _ = _make_service(configured=False)
        stats = await service.get_stats()
        assert stats.total_tracks == 0
        assert stats.total_albums == 0
        assert stats.total_artists == 0


class TestGetAlbumMatch:
    @pytest.mark.asyncio
    async def test_mbid_cache_hit(self):
        service, repo, _ = _make_service()
        service._mbid_to_plex_id["mbid-123"] = "plex-456"
        repo.get_album_metadata = AsyncMock(return_value=_album(key="plex-456"))
        repo.get_album_tracks = AsyncMock(return_value=[_track()])

        result = await service.get_album_match("mbid-123", "Album", "Artist")
        assert result.found is True
        assert result.plex_album_id == "plex-456"

    @pytest.mark.asyncio
    async def test_not_found(self):
        service, repo, _ = _make_service()
        repo.search = AsyncMock(return_value={"albums": [], "tracks": [], "artists": []})
        result = await service.get_album_match("", "Nonexistent", "Nobody")
        assert result.found is False

    @pytest.mark.asyncio
    async def test_no_sections_returns_not_found(self):
        service, _, _ = _make_service(configured=False)
        result = await service.get_album_match("mbid", "Album", "Artist")
        assert result.found is False


class TestLookupPlexId:
    def test_returns_cached_id(self):
        service, _, _ = _make_service()
        service._mbid_to_plex_id["mbid-1"] = "plex-1"
        assert service.lookup_plex_id("mbid-1") == "plex-1"

    def test_returns_none_when_not_cached(self):
        service, _, _ = _make_service()
        assert service.lookup_plex_id("mbid-missing") is None

"""Tests for deep discovery and analytics features."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.v1.schemas.navidrome import NavidromeArtistInfoSchema, NavidromeTrackInfo
from api.v1.schemas.jellyfin import JellyfinAlbumSummary
from api.v1.schemas.plex import PlexAnalyticsResponse, PlexHistoryResponse
from repositories.navidrome_models import SubsonicArtist, SubsonicArtistInfo, SubsonicSong
from repositories.jellyfin_models import JellyfinItem
from repositories.plex_models import PlexHistoryEntry
from services.navidrome_library_service import NavidromeLibraryService
from services.jellyfin_library_service import JellyfinLibraryService
from services.plex_library_service import PlexLibraryService


def _make_navidrome_service() -> tuple[NavidromeLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_album_list = AsyncMock(return_value=[])
    repo.get_album = AsyncMock()
    repo.get_artists = AsyncMock(return_value=[])
    repo.get_artist = AsyncMock()
    repo.get_starred = AsyncMock()
    repo.get_genres = AsyncMock(return_value=[])
    repo.search = AsyncMock()
    repo.get_top_songs = AsyncMock(return_value=[])
    repo.get_similar_songs = AsyncMock(return_value=[])
    repo.get_artist_info = AsyncMock(return_value=None)
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = MagicMock()
    service = NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)
    return service, repo


def _make_jellyfin_service() -> tuple[JellyfinLibraryService, MagicMock]:
    repo = MagicMock()
    repo.is_configured.return_value = True
    repo.get_similar_items = AsyncMock(return_value=[])
    repo.get_image_url = MagicMock(return_value=None)
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = MagicMock()
    service = JellyfinLibraryService(jellyfin_repo=repo, preferences_service=prefs)
    return service, repo


def _make_plex_service() -> tuple[PlexLibraryService, MagicMock]:
    repo = MagicMock()
    repo.is_configured.return_value = True
    repo.get_listening_history = AsyncMock(return_value=([], 0))
    repo.get_music_libraries = AsyncMock(return_value=[])
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = MagicMock()
    service = PlexLibraryService(plex_repo=repo, preferences_service=prefs)
    return service, repo


def _subsonic_song(id: str = "s1", title: str = "Song", artist: str = "Artist",
                   album: str = "Album", track: int = 1, duration: int = 200) -> SubsonicSong:
    return SubsonicSong(id=id, title=title, artist=artist, album=album,
                        track=track, duration=duration)


def _jellyfin_item(id: str = "j1", name: str = "Album", type: str = "MusicAlbum",
                   artist_name: str = "Artist") -> JellyfinItem:
    return JellyfinItem(id=id, name=name, type=type, artist_name=artist_name)


def _plex_history_entry(
    rating_key: str = "100",
    track_title: str = "Song",
    artist_name: str = "Artist",
    album_name: str = "Album",
    viewed_at: int = 1700000000,
    duration_ms: int = 200000,
) -> PlexHistoryEntry:
    return PlexHistoryEntry(
        rating_key=rating_key,
        track_title=track_title,
        artist_name=artist_name,
        album_name=album_name,
        album_rating_key="200",
        viewed_at=viewed_at,
        duration_ms=duration_ms,
        device_name="Chrome",
        player_platform="Web",
    )


class TestNavidromeTopSongs:
    @pytest.mark.asyncio
    async def test_returns_mapped_tracks(self):
        service, repo = _make_navidrome_service()
        repo.get_top_songs.return_value = [
            _subsonic_song("s1", "Hit Song", "Radiohead"),
            _subsonic_song("s2", "Another Hit", "Radiohead"),
        ]
        result = await service.get_top_songs("Radiohead")
        assert len(result) == 2
        assert isinstance(result[0], NavidromeTrackInfo)
        assert result[0].title == "Hit Song"
        repo.get_top_songs.assert_awaited_once_with("Radiohead", count=20)

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_top_songs.side_effect = Exception("Last.fm unavailable")
        result = await service.get_top_songs("Unknown Artist")
        assert result == []


class TestNavidromeSimilarSongs:
    @pytest.mark.asyncio
    async def test_returns_mapped_tracks(self):
        service, repo = _make_navidrome_service()
        repo.get_similar_songs.return_value = [_subsonic_song("s3", "Similar")]
        result = await service.get_similar_songs("s1")
        assert len(result) == 1
        assert result[0].title == "Similar"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_similar_songs.side_effect = Exception("Fail")
        result = await service.get_similar_songs("s1")
        assert result == []


class TestNavidromeArtistInfo:
    @pytest.mark.asyncio
    async def test_returns_info_schema(self):
        service, repo = _make_navidrome_service()
        repo.get_artist_info.return_value = SubsonicArtistInfo(
            biography="A great band.",
            musicBrainzId="mbid-123",
            smallImageUrl="http://img/sm.jpg",
            mediumImageUrl="http://img/md.jpg",
            largeImageUrl="http://img/lg.jpg",
            similarArtist=[SubsonicArtist(id="ar2", name="Similar Band")],
        )
        result = await service.get_artist_info("ar1")
        assert result is not None
        assert isinstance(result, NavidromeArtistInfoSchema)
        assert result.biography == "A great band."
        assert result.image_url == "http://img/lg.jpg"
        assert len(result.similar_artists) == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_not_available(self):
        service, repo = _make_navidrome_service()
        repo.get_artist_info.return_value = None
        result = await service.get_artist_info("ar1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_artist_info.side_effect = Exception("Fail")
        result = await service.get_artist_info("ar1")
        assert result is None


class TestJellyfinSimilarItems:
    @pytest.mark.asyncio
    async def test_returns_album_summaries(self):
        service, repo = _make_jellyfin_service()
        repo.get_similar_items.return_value = [
            _jellyfin_item("j1", "Similar Album"),
            _jellyfin_item("j2", "Another Similar"),
        ]
        result = await service.get_similar_items("seed-id")
        assert len(result) == 2
        assert isinstance(result[0], JellyfinAlbumSummary)
        assert result[0].name == "Similar Album"

    @pytest.mark.asyncio
    async def test_filters_non_music(self):
        service, repo = _make_jellyfin_service()
        repo.get_similar_items.return_value = [
            _jellyfin_item("j1", "Album", "MusicAlbum"),
            _jellyfin_item("j2", "Video", "Video"),
        ]
        result = await service.get_similar_items("seed-id")
        assert len(result) == 1
        assert result[0].name == "Album"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        service, repo = _make_jellyfin_service()
        repo.get_similar_items.side_effect = Exception("Fail")
        result = await service.get_similar_items("seed-id")
        assert result == []


class TestPlexHistory:
    @pytest.mark.asyncio
    async def test_returns_history_response(self):
        service, repo = _make_plex_service()
        repo.get_listening_history.return_value = (
            [_plex_history_entry("100", "Song 1"), _plex_history_entry("101", "Song 2")],
            50,
        )
        result = await service.get_history(limit=10)
        assert isinstance(result, PlexHistoryResponse)
        assert len(result.entries) == 2
        assert result.total == 50
        assert result.entries[0].track_title == "Song 1"

    @pytest.mark.asyncio
    async def test_returns_empty_history(self):
        service, repo = _make_plex_service()
        repo.get_listening_history.return_value = ([], 0)
        result = await service.get_history()
        assert result.entries == []
        assert result.total == 0


class TestPlexAnalytics:
    @pytest.mark.asyncio
    async def test_aggregation_with_entries(self):
        import time

        now_ts = int(time.time())
        entries = [
            _plex_history_entry("1", "Song A", "Artist X", "Album 1", now_ts, 180000),
            _plex_history_entry("2", "Song A", "Artist X", "Album 1", now_ts, 180000),
            _plex_history_entry("3", "Song B", "Artist Y", "Album 2", now_ts, 240000),
        ]
        service, repo = _make_plex_service()
        repo.get_listening_history.return_value = (entries, 3)
        result = await service.get_analytics()
        assert isinstance(result, PlexAnalyticsResponse)
        assert result.total_listens == 3
        assert result.entries_analyzed == 3
        assert result.is_complete is True
        assert result.top_artists[0].name == "Artist X"
        assert result.top_artists[0].play_count == 2
        assert result.top_tracks[0].name == "Song A"
        assert result.listens_last_7_days == 3
        assert result.total_hours > 0

    @pytest.mark.asyncio
    async def test_empty_history_analytics(self):
        service, repo = _make_plex_service()
        repo.get_listening_history.return_value = ([], 0)
        result = await service.get_analytics()
        assert result.total_listens == 0
        assert result.top_artists == []
        assert result.is_complete is True

    @pytest.mark.asyncio
    async def test_incomplete_flag_set(self):
        entries = [_plex_history_entry(str(i), f"Song {i}") for i in range(500)]
        service, repo = _make_plex_service()

        call_count = 0
        async def mock_history(limit: int = 50, offset: int = 0):
            nonlocal call_count
            call_count += 1
            if offset == 0:
                return (entries, 10000)
            return ([], 10000)

        repo.get_listening_history = AsyncMock(side_effect=mock_history)
        result = await service.get_analytics()
        assert result.entries_analyzed == 500
        assert result.is_complete is False

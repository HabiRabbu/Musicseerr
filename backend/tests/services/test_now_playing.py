"""Tests for now-playing and session service methods."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from repositories.plex_models import PlexSession
from repositories.navidrome_models import SubsonicNowPlayingEntry
from repositories.jellyfin_models import JellyfinSession
from services.plex_library_service import PlexLibraryService
from services.navidrome_library_service import NavidromeLibraryService
from services.jellyfin_library_service import JellyfinLibraryService


def _make_plex_service() -> tuple[PlexLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_sessions = AsyncMock(return_value=[])
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
    conn = MagicMock()
    conn.enabled = True
    conn.plex_url = "http://plex:32400"
    conn.plex_token = "tok"
    conn.music_library_ids = ["1"]
    prefs.get_plex_connection_raw.return_value = conn

    svc = PlexLibraryService(plex_repo=repo, preferences_service=prefs)
    return svc, repo


def _plex_session(**overrides) -> PlexSession:
    defaults = dict(
        session_id="sess1",
        user_name="alice",
        track_title="Song A",
        artist_name="Artist A",
        album_name="Album A",
        album_thumb="/library/metadata/200/thumb",
        player_device="iPhone",
        player_platform="iOS",
        player_state="playing",
        is_direct_play=True,
        progress_ms=60000,
        duration_ms=180000,
        audio_codec="flac",
        audio_channels=2,
        bitrate=1411,
    )
    defaults.update(overrides)
    return PlexSession(**defaults)


def _make_navidrome_service() -> tuple[NavidromeLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_now_playing = AsyncMock(return_value=[])
    repo.get_albums = AsyncMock(return_value=[])
    repo.get_album_info = AsyncMock()
    repo.get_album_tracks = AsyncMock(return_value=[])
    repo.get_starred = AsyncMock()
    repo.get_artists = AsyncMock(return_value=[])
    repo.get_artist = AsyncMock()
    repo.get_artist_info = AsyncMock()
    repo.search = AsyncMock()
    repo.get_genres = AsyncMock(return_value=[])
    repo.now_playing = AsyncMock(return_value=True)
    repo.get_playlists = AsyncMock(return_value=[])
    repo.get_playlist = AsyncMock()
    repo.get_random_songs = AsyncMock(return_value=[])

    prefs = MagicMock()
    prefs.get_navidrome_connection_raw.return_value = MagicMock(enabled=True)

    svc = NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)
    return svc, repo


def _navidrome_entry(**overrides) -> SubsonicNowPlayingEntry:
    defaults = dict(
        id="np1",
        title="Song N",
        artist="Artist N",
        album="Album N",
        albumId="al1",
        artistId="ar1",
        coverArt="cov1",
        duration=240,
        bitRate=320,
        suffix="mp3",
        username="bob",
        minutesAgo=2,
        playerId=1,
        playerName="Firefox",
    )
    defaults.update(overrides)
    return SubsonicNowPlayingEntry(**defaults)


def _make_jellyfin_service() -> tuple[JellyfinLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_sessions = AsyncMock(return_value=[])
    repo.get_recently_played = AsyncMock(return_value=[])
    repo.get_favorites = AsyncMock(return_value=[])
    repo.get_albums = AsyncMock(return_value=[])
    repo.get_artists = AsyncMock(return_value=[])
    repo.get_album = AsyncMock()
    repo.get_album_tracks = AsyncMock(return_value=[])
    repo.search = AsyncMock()
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_recently_added = AsyncMock(return_value=[])
    repo.get_most_played_artists = AsyncMock(return_value=[])
    repo.get_most_played_albums = AsyncMock(return_value=[])
    repo.get_playlists = AsyncMock(return_value=[])
    repo.get_playlist = AsyncMock()
    repo.get_image_url = MagicMock(return_value="https://jellyfin/Items/img/Primary")

    prefs = MagicMock()
    prefs.get_jellyfin_connection_raw.return_value = MagicMock(enabled=True)

    svc = JellyfinLibraryService(jellyfin_repo=repo, preferences_service=prefs)
    return svc, repo


def _jellyfin_session(**overrides) -> JellyfinSession:
    defaults = dict(
        session_id="jsess1",
        user_name="carol",
        device_name="Chrome",
        client_name="Jellyfin Web",
        now_playing_name="Song J",
        now_playing_artist="Artist J",
        now_playing_album="Album J",
        now_playing_album_id="jalb1",
        now_playing_item_id="jitem1",
        now_playing_image_tag="tag1",
        position_ticks=600_000_000,
        runtime_ticks=3_000_000_000,
        is_paused=False,
        is_muted=False,
        play_method="DirectPlay",
        audio_codec="aac",
        bitrate=256,
    )
    defaults.update(overrides)
    return JellyfinSession(**defaults)


class TestPlexGetSessions:
    @pytest.mark.asyncio
    async def test_returns_mapped_sessions(self):
        svc, repo = _make_plex_service()
        repo.get_sessions.return_value = [_plex_session()]

        result = await svc.get_sessions()

        assert len(result.sessions) == 1
        s = result.sessions[0]
        assert s.session_id == "sess1"
        assert s.user_name == "alice"
        assert s.track_title == "Song A"
        assert s.artist_name == "Artist A"
        assert s.cover_url == "/api/v1/plex/thumb//library/metadata/200/thumb"
        assert s.player_state == "playing"
        assert s.progress_ms == 60000
        assert s.duration_ms == 180000

    @pytest.mark.asyncio
    async def test_empty_sessions(self):
        svc, repo = _make_plex_service()
        repo.get_sessions.return_value = []

        result = await svc.get_sessions()

        assert result.sessions == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self):
        svc, repo = _make_plex_service()
        repo.get_sessions.side_effect = RuntimeError("Connection refused")

        result = await svc.get_sessions()

        assert result.sessions == []

    @pytest.mark.asyncio
    async def test_no_cover_when_no_album_thumb(self):
        svc, repo = _make_plex_service()
        repo.get_sessions.return_value = [_plex_session(album_thumb="")]

        result = await svc.get_sessions()

        assert result.sessions[0].cover_url == ""


class TestNavidromeGetNowPlaying:
    @pytest.mark.asyncio
    async def test_returns_mapped_entries(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.return_value = [_navidrome_entry()]

        result = await svc.get_now_playing()

        assert len(result.entries) == 1
        e = result.entries[0]
        assert e.user_name == "bob"
        assert e.track_name == "Song N"
        assert e.artist_name == "Artist N"
        assert e.album_name == "Album N"
        assert e.cover_art_id == "cov1"
        assert e.duration_seconds == 240
        assert e.minutes_ago == 2
        assert e.player_name == "Firefox"

    @pytest.mark.asyncio
    async def test_empty_entries(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.return_value = []

        result = await svc.get_now_playing()

        assert result.entries == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.side_effect = RuntimeError("timeout")

        result = await svc.get_now_playing()

        assert result.entries == []

    @pytest.mark.asyncio
    async def test_multiple_entries(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.return_value = [
            _navidrome_entry(username="bob"),
            _navidrome_entry(username="charlie", title="Song X"),
        ]

        result = await svc.get_now_playing()

        assert len(result.entries) == 2
        assert result.entries[0].user_name == "bob"
        assert result.entries[1].user_name == "charlie"


class TestJellyfinGetSessions:
    @pytest.mark.asyncio
    async def test_returns_mapped_sessions(self):
        svc, repo = _make_jellyfin_service()
        repo.get_sessions.return_value = [_jellyfin_session()]

        result = await svc.get_sessions()

        assert len(result.sessions) == 1
        s = result.sessions[0]
        assert s.session_id == "jsess1"
        assert s.user_name == "carol"
        assert s.track_name == "Song J"
        assert s.artist_name == "Artist J"
        assert s.device_name == "Chrome"
        assert s.cover_url == "/api/v1/jellyfin/image/jitem1"
        assert s.is_paused is False
        assert s.play_method == "DirectPlay"

    @pytest.mark.asyncio
    async def test_ticks_to_seconds_conversion(self):
        svc, repo = _make_jellyfin_service()
        repo.get_sessions.return_value = [_jellyfin_session(
            position_ticks=600_000_000,
            runtime_ticks=3_000_000_000,
        )]

        result = await svc.get_sessions()

        s = result.sessions[0]
        assert s.position_seconds == pytest.approx(60.0, rel=1e-3)
        assert s.duration_seconds == pytest.approx(300.0, rel=1e-3)

    @pytest.mark.asyncio
    async def test_empty_sessions(self):
        svc, repo = _make_jellyfin_service()
        repo.get_sessions.return_value = []

        result = await svc.get_sessions()

        assert result.sessions == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self):
        svc, repo = _make_jellyfin_service()
        repo.get_sessions.side_effect = RuntimeError("conn refused")

        result = await svc.get_sessions()

        assert result.sessions == []

    @pytest.mark.asyncio
    async def test_zero_ticks_returns_zero_seconds(self):
        svc, repo = _make_jellyfin_service()
        repo.get_sessions.return_value = [_jellyfin_session(
            position_ticks=0,
            runtime_ticks=0,
        )]

        result = await svc.get_sessions()

        s = result.sessions[0]
        assert s.position_seconds == 0.0
        assert s.duration_seconds == 0.0

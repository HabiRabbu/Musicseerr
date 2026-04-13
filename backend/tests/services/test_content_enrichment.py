"""Tests for lyrics, album info, and audio-quality enrichment."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from repositories.navidrome_models import SubsonicAlbumInfo, SubsonicLyrics
from repositories.jellyfin_models import JellyfinLyrics, JellyfinLyricLine
from services.navidrome_library_service import NavidromeLibraryService
from services.jellyfin_library_service import JellyfinLibraryService
from services.plex_library_service import PlexLibraryService
from repositories.plex_models import PlexTrack, PlexMedia, PlexPart


def _navidrome_service(
    album_info=None,
    lyrics=None,
    lyrics_by_id=None,
) -> NavidromeLibraryService:
    repo = MagicMock()
    repo.get_albums = AsyncMock(return_value=[])
    repo.get_recently_played = AsyncMock(return_value=[])
    repo.get_recently_added = AsyncMock(return_value=[])
    repo.get_starred_albums = AsyncMock(return_value=[])
    repo.get_starred_artists = AsyncMock(return_value=[])
    repo.get_starred_songs = AsyncMock(return_value=[])
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_album_count = AsyncMock(return_value=0)
    repo.get_track_count = AsyncMock(return_value=0)
    repo.get_artist_count = AsyncMock(return_value=0)
    repo.get_album_info = AsyncMock(return_value=album_info)
    repo.get_lyrics = AsyncMock(return_value=lyrics)
    repo.get_lyrics_by_song_id = AsyncMock(return_value=lyrics_by_id)
    prefs = MagicMock()
    return NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)


def _jellyfin_service(lyrics=None) -> JellyfinLibraryService:
    repo = MagicMock()
    repo.get_albums = AsyncMock(return_value=([], 0))
    repo.get_recently_added = AsyncMock(return_value=[])
    repo.get_most_played = AsyncMock(return_value=[])
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_track_count = AsyncMock(return_value=0)
    repo.get_artist_count = AsyncMock(return_value=0)
    repo.get_lyrics = AsyncMock(return_value=lyrics)
    prefs = MagicMock()
    return JellyfinLibraryService(jellyfin_repo=repo, preferences_service=prefs)


def _plex_service() -> PlexLibraryService:
    repo = MagicMock()
    repo.get_albums = AsyncMock(return_value=([], 0))
    repo.get_recently_added = AsyncMock(return_value=[])
    repo.get_recently_viewed = AsyncMock(return_value=[])
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_track_count = AsyncMock(return_value=0)
    repo.get_artist_count = AsyncMock(return_value=0)
    type(repo).stats_ttl = PropertyMock(return_value=600)
    prefs = MagicMock()
    conn = MagicMock()
    conn.enabled = True
    conn.plex_url = "http://plex:32400"
    conn.plex_token = "tok"
    conn.music_library_ids = ["1"]
    prefs.get_plex_connection_raw.return_value = conn
    return PlexLibraryService(plex_repo=repo, preferences_service=prefs)


@pytest.mark.asyncio
async def test_navidrome_album_info_returns_schema():
    info = SubsonicAlbumInfo(
        notes="Great album with <a>link</a>.",
        musicBrainzId="mb-123",
        lastFmUrl="https://last.fm/music/album",
        smallImageUrl="https://img/s.jpg",
        mediumImageUrl="https://img/m.jpg",
        largeImageUrl="https://img/l.jpg",
    )
    svc = _navidrome_service(album_info=info)
    result = await svc.get_album_info("album-1")
    assert result is not None
    assert result.album_id == "album-1"
    assert result.musicbrainz_id == "mb-123"
    assert result.lastfm_url == "https://last.fm/music/album"
    assert result.image_url == "https://img/l.jpg"
    assert "<a>" not in result.notes


@pytest.mark.asyncio
async def test_navidrome_album_info_returns_none_when_empty():
    info = SubsonicAlbumInfo()
    svc = _navidrome_service(album_info=info)
    result = await svc.get_album_info("album-1")
    assert result is None


@pytest.mark.asyncio
async def test_navidrome_album_info_returns_none_on_error():
    svc = _navidrome_service()
    svc._navidrome.get_album_info = AsyncMock(side_effect=RuntimeError("fail"))
    result = await svc.get_album_info("album-1")
    assert result is None


@pytest.mark.asyncio
async def test_navidrome_lyrics_by_song_id_first():
    lyrics = SubsonicLyrics(value="Hello world\nLine two", artist="A", title="T")
    svc = _navidrome_service(lyrics_by_id=lyrics)
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is not None
    assert "Hello world" in result.text


@pytest.mark.asyncio
async def test_navidrome_lyrics_fallback_to_artist_title():
    lyrics = SubsonicLyrics(value="Fallback lyrics", artist="A", title="T")
    svc = _navidrome_service(lyrics_by_id=None, lyrics=lyrics)
    svc._navidrome.get_lyrics_by_song_id = AsyncMock(side_effect=RuntimeError("not supported"))
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is not None
    assert result.text == "Fallback lyrics"


@pytest.mark.asyncio
async def test_navidrome_lyrics_returns_none_when_empty():
    lyrics = SubsonicLyrics(value="", artist="A", title="T")
    svc = _navidrome_service(lyrics_by_id=lyrics)
    svc._navidrome.get_lyrics = AsyncMock(return_value=SubsonicLyrics(value="", artist="A", title="T"))
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is None


@pytest.mark.asyncio
async def test_navidrome_lyrics_returns_none_on_all_errors():
    svc = _navidrome_service()
    svc._navidrome.get_lyrics_by_song_id = AsyncMock(side_effect=RuntimeError("fail"))
    svc._navidrome.get_lyrics = AsyncMock(side_effect=RuntimeError("fail"))
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is None


@pytest.mark.asyncio
async def test_jellyfin_lyrics_synced():
    lyrics = JellyfinLyrics(lines=[
        JellyfinLyricLine(text="Line one", start=50_000_000),
        JellyfinLyricLine(text="Line two", start=100_000_000),
    ])
    svc = _jellyfin_service(lyrics=lyrics)
    result = await svc.get_lyrics("item-1")
    assert result is not None
    assert result.is_synced is True
    assert len(result.lines) == 2
    assert result.lines[0].start_seconds == pytest.approx(5.0)
    assert result.lines[1].start_seconds == pytest.approx(10.0)
    assert "Line one" in result.lyrics_text


@pytest.mark.asyncio
async def test_jellyfin_lyrics_unsynced():
    lyrics = JellyfinLyrics(lines=[
        JellyfinLyricLine(text="Plain text", start=None),
    ])
    svc = _jellyfin_service(lyrics=lyrics)
    result = await svc.get_lyrics("item-1")
    assert result is not None
    assert result.is_synced is False
    assert result.lines[0].start_seconds is None


@pytest.mark.asyncio
async def test_jellyfin_lyrics_returns_none_when_unavailable():
    svc = _jellyfin_service(lyrics=None)
    result = await svc.get_lyrics("item-1")
    assert result is None


@pytest.mark.asyncio
async def test_jellyfin_lyrics_returns_none_on_error():
    svc = _jellyfin_service()
    svc._jellyfin.get_lyrics = AsyncMock(side_effect=RuntimeError("fail"))
    result = await svc.get_lyrics("item-1")
    assert result is None


def test_plex_track_to_info_extracts_audio_quality():
    track = PlexTrack(
        ratingKey="1",
        title="Song",
        index=1,
        parentIndex=1,
        duration=180000,
        parentTitle="Album",
        grandparentTitle="Artist",
        Media=[
            PlexMedia(
                bitrate=1411,
                audioCodec="flac",
                audioChannels=2,
                container="flac",
                Part=[PlexPart(key="/part/1")],
            )
        ],
    )
    svc = _plex_service()
    info = svc._track_to_info(track)
    assert info.codec == "flac"
    assert info.bitrate == 1411
    assert info.audio_channels == 2
    assert info.container == "flac"


def test_plex_track_to_info_handles_missing_media():
    track = PlexTrack(
        ratingKey="2",
        title="Song2",
        index=2,
        parentIndex=1,
        duration=120000,
        parentTitle="Album",
        grandparentTitle="Artist",
        Media=[],
    )
    svc = _plex_service()
    info = svc._track_to_info(track)
    assert info.codec is None
    assert info.bitrate is None
    assert info.audio_channels is None
    assert info.container is None

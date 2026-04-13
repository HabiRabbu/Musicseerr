from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import msgspec

from core.exceptions import NavidromeApiError, NavidromeAuthError, NavidromeSubsonicError


class SubsonicArtist(msgspec.Struct):
    id: str
    name: str
    albumCount: int = 0
    coverArt: str = ""
    musicBrainzId: str = ""


class SubsonicSong(msgspec.Struct):
    id: str
    title: str
    album: str = ""
    albumId: str = ""
    artist: str = ""
    artistId: str = ""
    track: int = 0
    discNumber: int = 1
    year: int = 0
    duration: int = 0
    bitRate: int = 0
    suffix: str = ""
    contentType: str = ""
    musicBrainzId: str = ""


class SubsonicAlbum(msgspec.Struct):
    id: str
    name: str
    artist: str = ""
    artistId: str = ""
    year: int = 0
    genre: str = ""
    songCount: int = 0
    duration: int = 0
    coverArt: str = ""
    musicBrainzId: str = ""
    song: list[SubsonicSong] | None = None


class SubsonicPlaylist(msgspec.Struct):
    id: str
    name: str
    songCount: int = 0
    duration: int = 0
    entry: list[SubsonicSong] | None = None


class SubsonicGenre(msgspec.Struct):
    name: str = ""
    songCount: int = 0
    albumCount: int = 0


class SubsonicSearchResult(msgspec.Struct):
    artist: list[SubsonicArtist] = msgspec.field(default_factory=list)
    album: list[SubsonicAlbum] = msgspec.field(default_factory=list)
    song: list[SubsonicSong] = msgspec.field(default_factory=list)


class StreamProxyResult(msgspec.Struct):
    status_code: int
    headers: dict[str, str]
    media_type: str
    body_chunks: AsyncIterator[bytes] | None = None


def parse_subsonic_response(data: dict[str, Any]) -> dict[str, Any]:
    resp = data.get("subsonic-response")
    if resp is None:
        raise NavidromeApiError("Missing subsonic-response envelope")
    status = resp.get("status", "")
    if status != "ok":
        error = resp.get("error", {})
        code = error.get("code", 0)
        message = error.get("message", "Unknown Subsonic API error")
        if code in (40, 41):
            raise NavidromeAuthError(message, code=code)
        raise NavidromeSubsonicError(message, code=code)
    return resp


def parse_artist(data: dict[str, Any]) -> SubsonicArtist:
    return SubsonicArtist(
        id=data.get("id", ""),
        name=data.get("name", "Unknown"),
        albumCount=data.get("albumCount", 0),
        coverArt=data.get("coverArt", ""),
        musicBrainzId=data.get("musicBrainzId", ""),
    )


def parse_song(data: dict[str, Any]) -> SubsonicSong:
    return SubsonicSong(
        id=data.get("id", ""),
        title=data.get("title", "Unknown"),
        album=data.get("album", ""),
        albumId=data.get("albumId", ""),
        artist=data.get("artist", ""),
        artistId=data.get("artistId", ""),
        track=data.get("track", 0),
        discNumber=data.get("discNumber", 1),
        year=data.get("year", 0),
        duration=data.get("duration", 0),
        bitRate=data.get("bitRate", 0),
        suffix=data.get("suffix", ""),
        contentType=data.get("contentType", ""),
        musicBrainzId=data.get("musicBrainzId", ""),
    )


def parse_album(data: dict[str, Any]) -> SubsonicAlbum:
    songs: list[SubsonicSong] | None = None
    raw_songs = data.get("song")
    if raw_songs is not None:
        songs = [parse_song(s) for s in raw_songs]

    return SubsonicAlbum(
        id=data.get("id", ""),
        name=data.get("name", data.get("title", "Unknown")),
        artist=data.get("artist", ""),
        artistId=data.get("artistId", ""),
        year=data.get("year", 0),
        genre=data.get("genre", ""),
        songCount=data.get("songCount", 0),
        duration=data.get("duration", 0),
        coverArt=data.get("coverArt", ""),
        musicBrainzId=data.get("musicBrainzId", ""),
        song=songs,
    )


def parse_genre(data: dict[str, Any]) -> SubsonicGenre:
    return SubsonicGenre(
        name=data.get("value", data.get("name", "")),
        songCount=data.get("songCount", 0),
        albumCount=data.get("albumCount", 0),
    )

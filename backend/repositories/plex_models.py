from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import msgspec

from core.exceptions import PlexApiError, PlexAuthError

logger = logging.getLogger(__name__)


class PlexGuid(msgspec.Struct):
    id: str = ""


class PlexGenreTag(msgspec.Struct):
    tag: str = ""


class PlexPart(msgspec.Struct):
    id: int = 0
    key: str = ""
    duration: int = 0
    file: str = ""
    size: int = 0
    container: str = ""


class PlexMedia(msgspec.Struct):
    id: int = 0
    duration: int = 0
    bitrate: int = 0
    audioCodec: str = ""
    audioChannels: int = 0
    container: str = ""
    Part: list[PlexPart] = msgspec.field(default_factory=list)


class PlexArtist(msgspec.Struct):
    ratingKey: str = ""
    title: str = ""
    thumb: str = ""
    addedAt: int = 0
    Guid: list[PlexGuid] = msgspec.field(default_factory=list)


class PlexAlbum(msgspec.Struct):
    ratingKey: str = ""
    title: str = ""
    parentTitle: str = ""
    parentRatingKey: str = ""
    year: int = 0
    thumb: str = ""
    addedAt: int = 0
    lastViewedAt: int = 0
    leafCount: int = 0
    Genre: list[PlexGenreTag] = msgspec.field(default_factory=list)
    Guid: list[PlexGuid] = msgspec.field(default_factory=list)


class PlexTrack(msgspec.Struct):
    ratingKey: str = ""
    title: str = ""
    parentTitle: str = ""
    grandparentTitle: str = ""
    parentRatingKey: str = ""
    index: int = 0
    parentIndex: int = 1
    duration: int = 0
    addedAt: int = 0
    Media: list[PlexMedia] = msgspec.field(default_factory=list)
    Guid: list[PlexGuid] = msgspec.field(default_factory=list)


class PlexPlaylist(msgspec.Struct):
    ratingKey: str = ""
    title: str = ""
    leafCount: int = 0
    duration: int = 0
    playlistType: str = ""


class PlexLibrarySection(msgspec.Struct):
    key: str = ""
    title: str = ""
    type: str = ""
    uuid: str = ""


class StreamProxyResult(msgspec.Struct):
    status_code: int
    headers: dict[str, str]
    media_type: str
    body_chunks: AsyncIterator[bytes] | None = None


class PlexOAuthPin(msgspec.Struct):
    id: int = 0
    code: str = ""
    authToken: str | None = None


def parse_plex_response(data: dict[str, Any]) -> dict[str, Any]:
    container = data.get("MediaContainer")
    if container is None:
        raise PlexApiError("Missing MediaContainer envelope in Plex response")
    return container


def parse_library_sections(container: dict[str, Any]) -> list[PlexLibrarySection]:
    raw = container.get("Directory", [])
    return [
        PlexLibrarySection(
            key=d.get("key", ""),
            title=d.get("title", ""),
            type=d.get("type", ""),
            uuid=d.get("uuid", ""),
        )
        for d in raw
    ]


def parse_artist(data: dict[str, Any]) -> PlexArtist:
    return PlexArtist(
        ratingKey=str(data.get("ratingKey", "")),
        title=data.get("title", "Unknown"),
        thumb=data.get("thumb", ""),
        addedAt=data.get("addedAt", 0),
        Guid=_parse_guids(data.get("Guid", [])),
    )


def parse_album(data: dict[str, Any]) -> PlexAlbum:
    return PlexAlbum(
        ratingKey=str(data.get("ratingKey", "")),
        title=data.get("title", "Unknown"),
        parentTitle=data.get("parentTitle", ""),
        parentRatingKey=str(data.get("parentRatingKey", "")),
        year=data.get("year", 0),
        thumb=data.get("thumb", ""),
        addedAt=data.get("addedAt", 0),
        lastViewedAt=data.get("lastViewedAt", 0),
        leafCount=data.get("leafCount", 0),
        Genre=_parse_genre_tags(data.get("Genre", [])),
        Guid=_parse_guids(data.get("Guid", [])),
    )


def parse_track(data: dict[str, Any]) -> PlexTrack:
    media_list: list[PlexMedia] = []
    for m in data.get("Media", []):
        parts = [
            PlexPart(
                id=p.get("id", 0),
                key=p.get("key", ""),
                duration=p.get("duration", 0),
                file=p.get("file", ""),
                size=p.get("size", 0),
                container=p.get("container", ""),
            )
            for p in m.get("Part", [])
        ]
        media_list.append(
            PlexMedia(
                id=m.get("id", 0),
                duration=m.get("duration", 0),
                bitrate=m.get("bitrate", 0),
                audioCodec=m.get("audioCodec", ""),
                audioChannels=m.get("audioChannels", 0),
                container=m.get("container", ""),
                Part=parts,
            )
        )
    return PlexTrack(
        ratingKey=str(data.get("ratingKey", "")),
        title=data.get("title", "Unknown"),
        parentTitle=data.get("parentTitle", ""),
        grandparentTitle=data.get("grandparentTitle", ""),
        parentRatingKey=str(data.get("parentRatingKey", "")),
        index=data.get("index", 0),
        parentIndex=data.get("parentIndex", 1),
        duration=data.get("duration", 0),
        addedAt=data.get("addedAt", 0),
        Media=media_list,
        Guid=_parse_guids(data.get("Guid", [])),
    )


def parse_playlist(data: dict[str, Any]) -> PlexPlaylist:
    return PlexPlaylist(
        ratingKey=str(data.get("ratingKey", "")),
        title=data.get("title", ""),
        leafCount=data.get("leafCount", 0),
        duration=data.get("duration", 0),
        playlistType=data.get("playlistType", ""),
    )


def _parse_guids(raw: list[dict[str, Any]] | None) -> list[PlexGuid]:
    if not raw:
        return []
    return [PlexGuid(id=g.get("id", "")) for g in raw]


def _parse_genre_tags(raw: list[dict[str, Any]] | None) -> list[PlexGenreTag]:
    if not raw:
        return []
    return [PlexGenreTag(tag=g.get("tag", "")) for g in raw]


def extract_mbid_from_guids(guids: list[PlexGuid], prefix: str = "mbid://") -> str:
    for guid in guids:
        if guid.id.startswith(prefix):
            return guid.id[len(prefix):]
    return ""

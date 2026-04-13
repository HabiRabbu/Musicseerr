from typing import Any

import msgspec


class JellyfinItem(msgspec.Struct):
    """Represents a Jellyfin library item (artist, album, or track)."""

    id: str
    name: str
    type: str
    artist_name: str | None = None
    album_name: str | None = None
    play_count: int = 0
    is_favorite: bool = False
    last_played: str | None = None
    image_tag: str | None = None
    parent_id: str | None = None
    album_id: str | None = None
    artist_id: str | None = None
    provider_ids: dict[str, str] | None = None
    index_number: int | None = None
    parent_index_number: int | None = None
    duration_ticks: int | None = None
    codec: str | None = None
    bitrate: int | None = None
    year: int | None = None
    sort_name: str | None = None
    album_count: int | None = None
    child_count: int | None = None
    date_created: str | None = None


class JellyfinUser(msgspec.Struct):
    id: str
    name: str


class PlaybackUrlResult(msgspec.Struct):
    url: str
    seekable: bool
    play_session_id: str
    play_method: str


def parse_item(item: dict[str, Any]) -> JellyfinItem:
    user_data = item.get("UserData", {})
    provider_ids = item.get("ProviderIds", {})

    artist_items = item.get("ArtistItems")

    artist_name = None
    if artist_items:
        artist_name = artist_items[0].get("Name")
    elif album_artist := item.get("AlbumArtist"):
        artist_name = album_artist

    return JellyfinItem(
        id=item.get("Id") or item.get("ItemId", ""),
        name=item.get("Name", "Unknown"),
        type=item.get("Type", "Unknown"),
        artist_name=artist_name,
        album_name=item.get("Album"),
        play_count=user_data.get("PlayCount", 0),
        is_favorite=user_data.get("IsFavorite", False),
        last_played=user_data.get("LastPlayedDate"),
        image_tag=item.get("ImageTags", {}).get("Primary"),
        parent_id=item.get("ParentId"),
        album_id=item.get("AlbumId"),
        artist_id=artist_items[0].get("Id") if artist_items else None,
        provider_ids=provider_ids if provider_ids else None,
        index_number=item.get("IndexNumber"),
        parent_index_number=item.get("ParentIndexNumber"),
        duration_ticks=item.get("RunTimeTicks"),
        codec=_extract_codec(item),
        bitrate=item.get("Bitrate"),
        year=item.get("ProductionYear"),
        sort_name=item.get("SortName"),
        album_count=item.get("AlbumCount"),
        child_count=item.get("ChildCount"),
        date_created=item.get("DateCreated"),
    )


def _extract_codec(item: dict[str, Any]) -> str | None:
    media_streams = item.get("MediaStreams")
    if media_streams:
        for stream in media_streams:
            if stream.get("Type") == "Audio":
                return stream.get("Codec")
    container = item.get("Container")
    return container if container else None


def parse_user(user: dict[str, Any]) -> JellyfinUser:
    return JellyfinUser(
        id=user.get("Id", ""),
        name=user.get("Name", "Unknown")
    )


class JellyfinSession(msgspec.Struct):
    session_id: str = ""
    user_name: str = ""
    device_name: str = ""
    client_name: str = ""
    now_playing_name: str = ""
    now_playing_artist: str = ""
    now_playing_album: str = ""
    now_playing_album_id: str = ""
    now_playing_item_id: str = ""
    now_playing_image_tag: str = ""
    position_ticks: int = 0
    runtime_ticks: int = 0
    is_paused: bool = False
    is_muted: bool = False
    play_method: str = ""
    audio_codec: str = ""
    bitrate: int = 0


class JellyfinLyricLine(msgspec.Struct):
    text: str = ""
    start: int | None = None


class JellyfinLyrics(msgspec.Struct):
    lines: list[JellyfinLyricLine] = msgspec.field(default_factory=list)


def parse_lyrics(data: dict[str, Any]) -> JellyfinLyrics | None:
    """Extract lyrics from a Jellyfin GET /Audio/{id}/Lyrics response (LyricDto)."""
    raw_lines = data.get("Lyrics", [])
    if not raw_lines:
        return None
    lines: list[JellyfinLyricLine] = []
    for line in raw_lines:
        lines.append(JellyfinLyricLine(
            text=line.get("Text", ""),
            start=line.get("Start"),
        ))
    return JellyfinLyrics(lines=lines)


def parse_jellyfin_sessions(data: list[dict[str, Any]]) -> list[JellyfinSession]:
    """Filter to audio-only sessions with an active NowPlayingItem."""
    sessions: list[JellyfinSession] = []
    for s in data:
        npi = s.get("NowPlayingItem")
        if npi is None:
            continue
        if npi.get("Type", "") != "Audio":
            continue
        play_state = s.get("PlayState", {})
        transcode = s.get("TranscodingInfo", {})
        artists = npi.get("Artists", [])
        artist_str = ", ".join(artists) if artists else npi.get("AlbumArtist", "")
        image_tags = npi.get("ImageTags", {})
        sessions.append(JellyfinSession(
            session_id=s.get("Id", ""),
            user_name=s.get("UserName", ""),
            device_name=s.get("DeviceName", ""),
            client_name=s.get("Client", ""),
            now_playing_name=npi.get("Name", ""),
            now_playing_artist=artist_str,
            now_playing_album=npi.get("Album", ""),
            now_playing_album_id=npi.get("AlbumId", ""),
            now_playing_item_id=npi.get("Id", ""),
            now_playing_image_tag=image_tags.get("Primary", ""),
            position_ticks=play_state.get("PositionTicks", 0) or 0,
            runtime_ticks=npi.get("RunTimeTicks", 0) or 0,
            is_paused=play_state.get("IsPaused", False),
            is_muted=play_state.get("IsMuted", False),
            play_method=transcode.get("Type", play_state.get("PlayMethod", "")),
            audio_codec=transcode.get("AudioCodec", _extract_codec(npi) or ""),
            bitrate=npi.get("Bitrate", 0) or 0,
        ))
    return sessions

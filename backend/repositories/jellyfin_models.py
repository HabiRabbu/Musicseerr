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
    duration_ticks: int | None = None
    codec: str | None = None
    bitrate: int | None = None
    year: int | None = None
    sort_name: str | None = None
    album_count: int | None = None
    child_count: int | None = None


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
        duration_ticks=item.get("RunTimeTicks"),
        codec=_extract_codec(item),
        bitrate=item.get("Bitrate"),
        year=item.get("ProductionYear"),
        sort_name=item.get("SortName"),
        album_count=item.get("AlbumCount"),
        child_count=item.get("ChildCount"),
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

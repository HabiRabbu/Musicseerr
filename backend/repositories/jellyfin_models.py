from dataclasses import dataclass
from typing import Any


@dataclass
class JellyfinItem:
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


@dataclass
class JellyfinUser:
    id: str
    name: str


def parse_item(item: dict[str, Any]) -> JellyfinItem:
    user_data = item.get("UserData", {})
    provider_ids = item.get("ProviderIds", {})

    artist_name = None
    if artists := item.get("ArtistItems"):
        artist_name = artists[0].get("Name") if artists else None
    elif album_artist := item.get("AlbumArtist"):
        artist_name = album_artist

    return JellyfinItem(
        id=item.get("Id", ""),
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
        artist_id=item.get("ArtistItems", [{}])[0].get("Id") if item.get("ArtistItems") else None,
        provider_ids=provider_ids if provider_ids else None,
    )


def parse_user(user: dict[str, Any]) -> JellyfinUser:
    return JellyfinUser(
        id=user.get("Id", ""),
        name=user.get("Name", "Unknown")
    )

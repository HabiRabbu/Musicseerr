import msgspec

from core.exceptions import ExternalServiceError


class LastFmToken(msgspec.Struct):
    token: str


class LastFmSession(msgspec.Struct):
    name: str
    key: str
    subscriber: int = 0


class LastFmTag(msgspec.Struct):
    name: str
    url: str = ""


class LastFmArtist(msgspec.Struct):
    name: str
    mbid: str | None = None
    playcount: int = 0
    listeners: int = 0
    url: str = ""


class LastFmAlbum(msgspec.Struct):
    name: str
    artist_name: str
    mbid: str | None = None
    playcount: int = 0
    listeners: int = 0
    url: str = ""
    image_url: str = ""


class LastFmTrack(msgspec.Struct):
    name: str
    artist_name: str
    mbid: str | None = None
    playcount: int = 0
    listeners: int = 0
    url: str = ""


class LastFmSimilarArtist(msgspec.Struct):
    name: str
    mbid: str | None = None
    match: float = 0.0
    url: str = ""


class LastFmArtistInfo(msgspec.Struct):
    name: str
    mbid: str | None = None
    listeners: int = 0
    playcount: int = 0
    url: str = ""
    bio_summary: str = ""
    tags: list[LastFmTag] | None = None
    similar: list[LastFmSimilarArtist] | None = None


class LastFmAlbumTrack(msgspec.Struct):
    name: str
    duration: int = 0
    rank: int = 0
    url: str = ""


class LastFmAlbumInfo(msgspec.Struct):
    name: str
    artist_name: str
    mbid: str | None = None
    listeners: int = 0
    playcount: int = 0
    url: str = ""
    image_url: str = ""
    summary: str = ""
    tags: list[LastFmTag] | None = None
    tracks: list[LastFmAlbumTrack] | None = None


class LastFmRecentTrack(msgspec.Struct):
    track_name: str
    artist_name: str
    album_name: str = ""
    artist_mbid: str | None = None
    album_mbid: str | None = None
    timestamp: int = 0
    now_playing: bool = False
    image_url: str = ""


class LastFmLovedTrack(msgspec.Struct):
    track_name: str
    artist_name: str
    album_name: str = ""
    track_mbid: str | None = None
    artist_mbid: str | None = None
    url: str = ""
    image_url: str = ""


ALLOWED_LASTFM_PERIOD = [
    "overall", "7day", "1month", "3month", "6month", "12month",
]


def parse_weekly_album_chart_item(item: dict) -> "LastFmAlbum":
    artist = item.get("artist", {})
    artist_name = artist.get("#text", "") if isinstance(artist, dict) else str(artist)
    return LastFmAlbum(
        name=item.get("name", ""),
        artist_name=artist_name,
        mbid=item.get("mbid") or None,
        playcount=_safe_int(item.get("playcount")),
        url=item.get("url", ""),
        image_url=_extract_image(item.get("image")),
    )


def parse_token(data: dict) -> LastFmToken:
    token_value = data.get("token")
    if not token_value:
        raise ExternalServiceError("Last.fm auth.getToken response missing 'token'")
    return LastFmToken(token=token_value)


def parse_session(data: dict) -> LastFmSession:
    session_data = data.get("session", data)
    name = session_data.get("name")
    key = session_data.get("key")
    if not name or not key:
        raise ExternalServiceError("Last.fm auth.getSession response missing 'name' or 'key'")
    return LastFmSession(
        name=name,
        key=key,
        subscriber=int(session_data.get("subscriber", 0)),
    )


def _extract_image(images: list[dict] | None, size: str = "extralarge") -> str:
    if not images:
        return ""
    for img in images:
        if img.get("size") == size:
            return img.get("#text", "")
    return images[-1].get("#text", "") if images else ""


def _safe_int(value: str | int | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: str | float | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_top_artist(item: dict) -> LastFmArtist:
    return LastFmArtist(
        name=item.get("name", ""),
        mbid=item.get("mbid") or None,
        playcount=_safe_int(item.get("playcount")),
        listeners=_safe_int(item.get("listeners")),
        url=item.get("url", ""),
    )


def parse_top_album(item: dict) -> LastFmAlbum:
    artist = item.get("artist", {})
    artist_name = artist.get("name", "") if isinstance(artist, dict) else str(artist)
    return LastFmAlbum(
        name=item.get("name", ""),
        artist_name=artist_name,
        mbid=item.get("mbid") or None,
        playcount=_safe_int(item.get("playcount")),
        listeners=_safe_int(item.get("listeners")),
        url=item.get("url", ""),
        image_url=_extract_image(item.get("image")),
    )


def parse_top_track(item: dict) -> LastFmTrack:
    artist = item.get("artist", {})
    artist_name = artist.get("name", "") if isinstance(artist, dict) else str(artist)
    return LastFmTrack(
        name=item.get("name", ""),
        artist_name=artist_name,
        mbid=item.get("mbid") or None,
        playcount=_safe_int(item.get("playcount")),
        listeners=_safe_int(item.get("listeners")),
        url=item.get("url", ""),
    )


def parse_similar_artist(item: dict) -> LastFmSimilarArtist:
    return LastFmSimilarArtist(
        name=item.get("name", ""),
        mbid=item.get("mbid") or None,
        match=_safe_float(item.get("match")),
        url=item.get("url", ""),
    )


def parse_artist_info(data: dict) -> LastFmArtistInfo:
    artist = data.get("artist", {})
    stats = artist.get("stats", {})
    tags_data = artist.get("tags", {}).get("tag", [])
    similar_data = artist.get("similar", {}).get("artist", [])
    bio = artist.get("bio", {})
    return LastFmArtistInfo(
        name=artist.get("name", ""),
        mbid=artist.get("mbid") or None,
        listeners=_safe_int(stats.get("listeners")),
        playcount=_safe_int(stats.get("playcount")),
        url=artist.get("url", ""),
        bio_summary=bio.get("summary", ""),
        tags=[LastFmTag(name=t.get("name", ""), url=t.get("url", "")) for t in tags_data],
        similar=[parse_similar_artist(s) for s in similar_data],
    )


def parse_album_info(data: dict) -> LastFmAlbumInfo:
    album = data.get("album", {})
    tags_data = album.get("tags", {}).get("tag", [])
    tracks_data = album.get("tracks", {}).get("track", [])
    wiki = album.get("wiki", {})
    tracks = [
        LastFmAlbumTrack(
            name=t.get("name", ""),
            duration=_safe_int(t.get("duration")),
            rank=_safe_int(t.get("@attr", {}).get("rank")),
            url=t.get("url", ""),
        )
        for t in tracks_data
    ] if tracks_data else None
    return LastFmAlbumInfo(
        name=album.get("name", ""),
        artist_name=album.get("artist", ""),
        mbid=album.get("mbid") or None,
        listeners=_safe_int(album.get("listeners")),
        playcount=_safe_int(album.get("playcount")),
        url=album.get("url", ""),
        image_url=_extract_image(album.get("image")),
        summary=wiki.get("summary", ""),
        tags=[LastFmTag(name=t.get("name", ""), url=t.get("url", "")) for t in tags_data],
        tracks=tracks,
    )


def parse_recent_track(item: dict) -> LastFmRecentTrack:
    artist = item.get("artist", {})
    album = item.get("album", {})
    date = item.get("date", {})
    attr = item.get("@attr", {})
    return LastFmRecentTrack(
        track_name=item.get("name", ""),
        artist_name=artist.get("#text", "") if isinstance(artist, dict) else str(artist),
        album_name=album.get("#text", "") if isinstance(album, dict) else str(album),
        artist_mbid=artist.get("mbid") or None if isinstance(artist, dict) else None,
        album_mbid=album.get("mbid") or None if isinstance(album, dict) else None,
        timestamp=_safe_int(date.get("uts")) if isinstance(date, dict) else 0,
        now_playing=attr.get("nowplaying") == "true",
        image_url=_extract_image(item.get("image")),
    )


def parse_loved_track(item: dict) -> LastFmLovedTrack:
    artist = item.get("artist", {})
    album = item.get("album", {})
    return LastFmLovedTrack(
        track_name=item.get("name", ""),
        artist_name=artist.get("name", "") if isinstance(artist, dict) else str(artist),
        album_name=album.get("#text", "") if isinstance(album, dict) else str(album),
        track_mbid=item.get("mbid") or None,
        artist_mbid=artist.get("mbid") if isinstance(artist, dict) else None,
        url=item.get("url", ""),
        image_url=_extract_image(item.get("image")),
    )

from typing import Any, Optional, Callable

_PLATFORM_PATTERNS = {
    "instagram.com": "Instagram",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "facebook.com": "Facebook",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "spotify.com": "Spotify",
    "deezer.com": "Deezer",
    "apple.com": "Apple Music",
    "music.apple.com": "Apple Music",
    "tidal.com": "Tidal",
    "amazon.": "Amazon",
    "bandcamp.com": "Bandcamp",
}

_LINK_TYPE_LABELS = {
    "official homepage": "Official Website",
    "wikipedia": "Wikipedia",
    "wikidata": "Wikidata",
    "discogs": "Discogs",
    "allmusic": "AllMusic",
    "bandcamp": "Bandcamp",
    "last.fm": "Last.fm",
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
    "instagram": "Instagram",
    "twitter": "Twitter",
    "facebook": "Facebook",
}


def detect_platform(url: str, rel_type: str) -> str:
    url_lower = url.lower()
    for pattern, platform in _PLATFORM_PATTERNS.items():
        if pattern in url_lower:
            return platform
    if rel_type == "social network":
        return "Social Media"
    elif rel_type == "free streaming":
        return "Streaming"
    elif rel_type == "purchase for download":
        return "Purchase"
    return _LINK_TYPE_LABELS.get(rel_type, rel_type.title())


def extract_tags(mb_artist: dict[str, Any], limit: int = 10) -> list[str]:
    tags = []
    if mb_tags := mb_artist.get("tag-list", []):
        tags = [tag.get("name") for tag in mb_tags if tag.get("name")][:limit]
    return tags


def extract_aliases(mb_artist: dict[str, Any], limit: int = 10) -> list[str]:
    aliases = []
    if mb_aliases := mb_artist.get("alias-list", []):
        aliases = [
            alias.get("alias") or alias.get("name")
            for alias in mb_aliases
            if alias.get("alias") or alias.get("name")
        ][:limit]
    return aliases


def extract_life_span(mb_artist: dict[str, Any]) -> Optional[dict[str, Any]]:
    if life_span := mb_artist.get("life-span"):
        return {
            "begin": life_span.get("begin"),
            "end": life_span.get("end"),
            "ended": life_span.get("ended")
        }
    return None


def extract_external_links(mb_artist: dict[str, Any]) -> list[dict[str, str]]:
    external_links = []
    seen_urls = set()
    if url_rels := mb_artist.get("url-relation-list", []):
        for url_rel in url_rels:
            rel_type = url_rel.get("type", "")
            target_url = url_rel.get("target", "")
            if not target_url or target_url in seen_urls:
                continue
            label = detect_platform(target_url, rel_type)
            external_links.append({"type": rel_type, "url": target_url, "label": label})
            seen_urls.add(target_url)
    return external_links


def categorize_release_groups(
    mb_artist: dict[str, Any],
    album_mbids: set[str],
    included_primary_types: Optional[set[str]] = None,
    included_secondary_types: Optional[set[str]] = None,
    requested_mbids: Optional[set[str]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if included_primary_types is None:
        included_primary_types = {"album", "single", "ep", "broadcast", "other"}
    if requested_mbids is None:
        requested_mbids = set()
    albums = []
    singles = []
    eps = []
    if rg_list := mb_artist.get("release-group-list", []):
        for rg in rg_list:
            rg_id = rg.get("id")
            primary_type = (rg.get("primary-type") or "").lower()
            if primary_type not in included_primary_types:
                continue
            if included_secondary_types is not None:
                secondary_types = set(map(str.lower, rg.get("secondary-type-list", []) or []))
                if not secondary_types:
                    if "studio" not in included_secondary_types:
                        continue
                elif not secondary_types.intersection(included_secondary_types):
                    continue
            rg_id_lower = rg_id.lower() if rg_id else ""
            in_library = rg_id_lower in album_mbids if rg_id else False
            requested = rg_id_lower in requested_mbids if rg_id and not in_library else False
            rg_data = {
                "id": rg_id,
                "title": rg.get("title"),
                "type": rg.get("primary-type"),
                "first_release_date": rg.get("first-release-date"),
                "in_library": in_library,
                "requested": requested,
            }
            if date := rg_data.get("first_release_date"):
                try:
                    rg_data["year"] = int(date.split("-")[0])
                except (ValueError, AttributeError):
                    pass
            if primary_type == "album":
                albums.append(rg_data)
            elif primary_type == "single":
                singles.append(rg_data)
            elif primary_type == "ep":
                eps.append(rg_data)
        for lst in [albums, singles, eps]:
            lst.sort(key=lambda x: (x.get("year") is None, -(x.get("year") or 0)))
    return albums, singles, eps


def categorize_lidarr_albums(
    lidarr_albums: list[dict[str, Any]],
    included_primary_types: set[str],
    included_secondary_types: set[str],
) -> tuple[list[dict], list[dict], list[dict]]:
    albums = []
    singles = []
    eps = []
    for album in lidarr_albums:
        album_type = (album.get("album_type") or "").lower()
        secondary_types = set(map(str.lower, album.get("secondary_types", []) or []))
        if album_type not in included_primary_types:
            continue
        if included_secondary_types:
            if not secondary_types:
                if "studio" not in included_secondary_types:
                    continue
            elif not secondary_types.intersection(included_secondary_types):
                continue
        mbid = album.get("mbid", "")
        track_file_count = album.get("track_file_count", 0)
        monitored = album.get("monitored", False)
        in_library = track_file_count > 0
        requested = monitored and track_file_count == 0
        album_data = {
            "id": mbid,
            "title": album.get("title"),
            "type": album.get("album_type"),
            "first_release_date": album.get("release_date"),
            "year": album.get("year"),
            "in_library": in_library,
            "requested": requested,
        }
        if album_type == "album":
            albums.append(album_data)
        elif album_type == "single":
            singles.append(album_data)
        elif album_type == "ep":
            eps.append(album_data)
    for lst in [albums, singles, eps]:
        lst.sort(key=lambda x: (x.get("year") is None, -(x.get("year") or 0)))
    return albums, singles, eps


def extract_wiki_info(
    mb_artist: dict[str, Any],
    get_wikidata_id_fn: Callable[[str], Optional[str]]
) -> tuple[Optional[str], list[str]]:
    wikidata_id = None
    wiki_urls = []
    if url_rels := mb_artist.get("url-relation-list", []):
        for url_rel in url_rels:
            url_type = url_rel.get("type")
            wiki_url = url_rel.get("target")
            if not wiki_url:
                continue
            if url_type == "wikidata" and not wikidata_id:
                wikidata_id = get_wikidata_id_fn(wiki_url)
            if url_type in ("wikipedia", "wikidata"):
                wiki_urls.append(wiki_url)
    return wikidata_id, wiki_urls


def build_base_artist_info(
    mb_artist: dict[str, Any],
    artist_id: str,
    in_library: bool,
    tags: list[str],
    aliases: list[str],
    life_span: Optional[dict[str, Any]],
    external_links: list,
    albums: list[dict],
    singles: list[dict],
    eps: list[dict],
    description: Optional[str] = None,
    image: Optional[str] = None,
    release_group_count: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "name": mb_artist.get("name", "Unknown Artist"),
        "musicbrainz_id": artist_id,
        "disambiguation": mb_artist.get("disambiguation"),
        "type": mb_artist.get("type"),
        "country": mb_artist.get("country"),
        "life_span": life_span,
        "description": description,
        "image": image,
        "tags": tags,
        "aliases": aliases,
        "external_links": external_links,
        "in_library": in_library,
        "albums": albums,
        "singles": singles,
        "eps": eps,
        "release_group_count": release_group_count or mb_artist.get("release-group-count", 0),
    }

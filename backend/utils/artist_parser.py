"""Parse and extract artist data from MusicBrainz responses."""
from typing import Any, Optional

# Platform detection mapping
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


def extract_tags(mb_artist: dict[str, Any], limit: int = 10) -> list[str]:
    """Extract tags from artist data.
    
    Args:
        mb_artist: MusicBrainz artist dict
        limit: Maximum number of tags to return
    
    Returns:
        List of tag names
    """
    tags = []
    if mb_tags := mb_artist.get("tag-list", []):
        tags = [tag.get("name") for tag in mb_tags if tag.get("name")][:limit]
    return tags


def extract_aliases(mb_artist: dict[str, Any], limit: int = 10) -> list[str]:
    """Extract aliases from artist data.
    
    Args:
        mb_artist: MusicBrainz artist dict
        limit: Maximum number of aliases to return
    
    Returns:
        List of alias names
    """
    aliases = []
    if mb_aliases := mb_artist.get("alias-list", []):
        aliases = [
            alias.get("alias") or alias.get("name")
            for alias in mb_aliases
            if alias.get("alias") or alias.get("name")
        ][:limit]
    return aliases


def extract_life_span(mb_artist: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Extract life span information from artist data.
    
    Args:
        mb_artist: MusicBrainz artist dict
    
    Returns:
        Dict with begin, end, and ended keys, or None
    """
    if life_span := mb_artist.get("life-span"):
        return {
            "begin": life_span.get("begin"),
            "end": life_span.get("end"),
            "ended": life_span.get("ended")
        }
    return None


def _detect_platform(url: str, rel_type: str) -> str:
    """Detect platform from URL and relationship type."""
    url_lower = url.lower()
    
    # Check URL patterns first
    for pattern, platform in _PLATFORM_PATTERNS.items():
        if pattern in url_lower:
            return platform
    
    # Fallback to relationship type
    if rel_type == "social network":
        return "Social Media"
    elif rel_type == "free streaming":
        return "Streaming"
    elif rel_type == "purchase for download":
        return "Purchase"
    
    # Use label mapping or title-case the type
    return _LINK_TYPE_LABELS.get(rel_type, rel_type.title())


def extract_external_links(mb_artist: dict[str, Any]) -> list[dict[str, str]]:
    """Extract external links from artist data.
    
    Args:
        mb_artist: MusicBrainz artist dict
    
    Returns:
        List of link dicts with type, url, and label keys
    """
    external_links = []
    seen_urls = set()
    
    if url_rels := mb_artist.get("url-relation-list", []):
        for url_rel in url_rels:
            rel_type = url_rel.get("type", "")
            target_url = url_rel.get("target", "")
            
            if not target_url or target_url in seen_urls:
                continue
            
            label = _detect_platform(target_url, rel_type)
            
            external_links.append({
                "type": rel_type,
                "url": target_url,
                "label": label
            })
            seen_urls.add(target_url)
    
    return external_links


def categorize_release_groups(
    mb_artist: dict[str, Any],
    album_mbids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Categorize release groups into albums, singles, and EPs.
    
    Args:
        mb_artist: MusicBrainz artist dict
        album_mbids: Set of MBIDs that are in the user's library
    
    Returns:
        Tuple of (albums, singles, eps) lists
    """
    albums = []
    singles = []
    eps = []
    
    if rg_list := mb_artist.get("release-group-list", []):
        for rg in rg_list:
            rg_id = rg.get("id")
            primary_type = (rg.get("primary-type") or "").lower()
            
            rg_data = {
                "id": rg_id,
                "title": rg.get("title"),
                "type": rg.get("primary-type"),
                "first_release_date": rg.get("first-release-date"),
                "in_library": rg_id.lower() in album_mbids if rg_id else False,
            }
            
            # Extract year from date
            if date := rg_data.get("first_release_date"):
                try:
                    rg_data["year"] = int(date.split("-")[0])
                except (ValueError, AttributeError):
                    pass
            
            # Categorize by type
            if primary_type == "album":
                albums.append(rg_data)
            elif primary_type == "single":
                singles.append(rg_data)
            elif primary_type == "ep":
                eps.append(rg_data)
        
        # Sort each list by year (newest first, None at end)
        for lst in [albums, singles, eps]:
            lst.sort(key=lambda x: (x.get("year") is None, -(x.get("year") or 0)))
    
    return albums, singles, eps

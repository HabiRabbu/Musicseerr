from typing import Any


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


def extract_life_span(mb_artist: dict[str, Any]) -> dict[str, Any] | None:
    if ls := mb_artist.get("life-span"):
        return {
            "begin": ls.get("begin"),
            "end": ls.get("end"),
            "ended": ls.get("ended")
        }
    return None


def detect_platform_from_url(url: str, rel_type: str) -> str:
    url_lower = url.lower()
    
    if rel_type == "social network":
        if "instagram.com" in url_lower:
            return "Instagram"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "Twitter"
        elif "facebook.com" in url_lower:
            return "Facebook"
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "YouTube"
        else:
            return "Social Media"
    
    if rel_type == "free streaming":
        if "spotify.com" in url_lower:
            return "Spotify"
        elif "deezer.com" in url_lower:
            return "Deezer"
        elif "apple.com" in url_lower or "music.apple.com" in url_lower:
            return "Apple Music"
        elif "tidal.com" in url_lower:
            return "Tidal"
        else:
            return "Streaming"
    
    if rel_type == "purchase for download":
        if "itunes.apple.com" in url_lower or "music.apple.com" in url_lower:
            return "Apple Music"
        elif "amazon." in url_lower:
            return "Amazon"
        elif "bandcamp.com" in url_lower:
            return "Bandcamp"
        else:
            return "Purchase"
    
    link_type_labels = {
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
    
    return link_type_labels.get(rel_type, rel_type.title())


def extract_external_links(mb_artist: dict[str, Any]) -> list[dict[str, str]]:
    external_links = []
    seen_urls = set()
    
    if url_rels := mb_artist.get("url-relation-list", []):
        for url_rel in url_rels:
            rel_type = url_rel.get("type", "")
            target_url = url_rel.get("target", "")
            
            if not target_url or target_url in seen_urls:
                continue
            
            label = detect_platform_from_url(target_url, rel_type)
            
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
    albums = []
    singles = []
    eps = []
    
    if rg_list := mb_artist.get("release-group-list", []):
        for rg in rg_list:
            rg_id = rg.get("id")
            primary_type = rg.get("primary-type", "").lower()
            
            rg_data = {
                "id": rg_id,
                "title": rg.get("title"),
                "type": rg.get("primary-type"),
                "first_release_date": rg.get("first-release-date"),
                "in_library": rg_id.lower() in album_mbids if rg_id else False,
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

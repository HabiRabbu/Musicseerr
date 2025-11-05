"""Centralized cache key generation for consistent, sorted, testable cache keys."""
from typing import Optional


def _sort_params(**kwargs) -> str:
    """Sort parameters for consistent key generation."""
    return ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)


def mb_artist_search_key(query: str, limit: int, offset: int) -> str:
    """Generate cache key for MusicBrainz artist search."""
    return f"mb:artist:search:{query}:{limit}:{offset}"


def mb_album_search_key(
    query: str,
    limit: int,
    offset: int,
    included_secondary_types: Optional[set[str]] = None
) -> str:
    """Generate cache key for MusicBrainz album search."""
    types_str = ",".join(sorted(included_secondary_types)) if included_secondary_types else "none"
    return f"mb:album:search:{query}:{limit}:{offset}:{types_str}"


def mb_artist_detail_key(mbid: str) -> str:
    """Generate cache key for MusicBrainz artist details."""
    return f"mb:artist:detail:{mbid}"


def mb_release_group_key(mbid: str, includes: Optional[list[str]] = None) -> str:
    """Generate cache key for MusicBrainz release group."""
    includes_str = ",".join(sorted(includes)) if includes else "default"
    return f"mb:rg:detail:{mbid}:{includes_str}"


def mb_release_key(release_id: str, includes: Optional[list[str]] = None) -> str:
    """Generate cache key for MusicBrainz release."""
    includes_str = ",".join(sorted(includes)) if includes else "default"
    return f"mb:release:detail:{release_id}:{includes_str}"


def lidarr_library_mbids_key(include_release_ids: bool = False) -> str:
    """Generate cache key for Lidarr library MBIDs."""
    suffix = "with_releases" if include_release_ids else "albums_only"
    return f"lidarr:library:mbids:{suffix}"


def lidarr_artist_mbids_key() -> str:
    """Generate cache key for Lidarr artist MBIDs."""
    return "lidarr:artists:mbids"


def lidarr_status_key() -> str:
    """Generate cache key for Lidarr status."""
    return "lidarr:status"


def wikidata_artist_image_key(wikidata_id: str) -> str:
    """Generate cache key for Wikidata artist image."""
    return f"wikidata:image:{wikidata_id}"


def wikidata_url_key(artist_id: str) -> str:
    """Generate cache key for artist Wikidata URL."""
    return f"wikidata:url:{artist_id}"


def wikipedia_extract_key(url: str) -> str:
    """Generate cache key for Wikipedia extract."""
    return f"wikipedia:extract:{url}"


def preferences_key() -> str:
    """Generate cache key for preferences."""
    return "preferences:current"

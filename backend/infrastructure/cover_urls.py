from typing import Optional

from infrastructure.validators import is_valid_mbid


def release_group_cover_url(release_group_mbid: Optional[str], size: int = 500) -> Optional[str]:
    if not is_valid_mbid(release_group_mbid):
        return None
    return f"/api/covers/release-group/{release_group_mbid}?size={size}"


def artist_cover_url(artist_mbid: Optional[str], size: int = 500) -> Optional[str]:
    if not is_valid_mbid(artist_mbid):
        return None
    return f"/api/covers/artist/{artist_mbid}?size={size}"


def prefer_release_group_cover_url(
    release_group_mbid: Optional[str],
    fallback_url: Optional[str] = None,
    size: int = 500,
) -> Optional[str]:
    return release_group_cover_url(release_group_mbid, size=size) or fallback_url


def prefer_artist_cover_url(
    artist_mbid: Optional[str],
    fallback_url: Optional[str] = None,
    size: int = 500,
) -> Optional[str]:
    return artist_cover_url(artist_mbid, size=size) or fallback_url

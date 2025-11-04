"""Cover Art Archive and artist image fetching."""
import asyncio
import logging
from pathlib import Path
from typing import Optional

import aiofiles
import musicbrainzngs

from http_client import client
from utils.cache import get_cache
from utils import wikidata

logger = logging.getLogger(__name__)

_cache = get_cache()
COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"
CACHE_DIR = Path("/app/cache/covers")

CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def _write_cache(
    file_path: Path,
    content: bytes,
    content_type: str,
    extra_meta: Optional[dict[str, str]] = None,
) -> None:
    """Write content to disk cache with metadata."""
    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        async with aiofiles.open(f"{file_path}.meta", "w") as m:
            await m.write(content_type)
        
        if extra_meta:
            for key, value in extra_meta.items():
                async with aiofiles.open(f"{file_path}.{key}", "w") as meta_file:
                    await meta_file.write(value)
    
    except Exception as e:
        logger.warning(f"Failed to write cache: {e}")


async def _read_cache(
    file_path: Path,
    extra_keys: Optional[list[str]] = None,
) -> Optional[tuple]:
    """Read content from disk cache."""
    try:
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        
        async with aiofiles.open(f"{file_path}.meta", "r") as m:
            content_type = (await m.read()).strip()
        
        result = [content, content_type]
        
        if extra_keys:
            for key in extra_keys:
                async with aiofiles.open(f"{file_path}.{key}", "r") as meta_file:
                    result.append((await meta_file.read()).strip())
        
        return tuple(result)
    
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


async def get_artist_image(artist_id: str) -> Optional[tuple[bytes, str, str]]:
    """Get artist image from Wikidata.
    
    Args:
        artist_id: MusicBrainz artist ID
    
    Returns:
        Tuple of (image_data, content_type, wikidata_id) or None
    """
    file_path = CACHE_DIR / f"artist_{artist_id}.bin"
    
    if cached := await _read_cache(file_path, ["wikidata_id"]):
        return cached
    
    cache_key = f"artist_wikidata:{artist_id}"
    wikidata_url = await _cache.get(cache_key)
    
    if wikidata_url is None:
        try:
            artist_data = await asyncio.to_thread(
                musicbrainzngs.get_artist_by_id,
                artist_id,
                includes=["url-rels"]
            )
            
            if artist := artist_data.get("artist"):
                url_relations = artist.get("url-relation-list", [])
                for url_rel in url_relations:
                    if url_rel.get("type") == "wikidata":
                        wikidata_url = url_rel.get("target")
                        break
            
            ttl = 86400 if wikidata_url else 3600
            await _cache.set(cache_key, wikidata_url, ttl_seconds=ttl)
        
        except Exception as e:
            logger.error(f"Failed to fetch artist metadata for {artist_id}: {e}")
            return None
    
    if not wikidata_url:
        return None
    
    try:
        wikidata_id = await wikidata.get_wikidata_id_from_url(wikidata_url)
        if not wikidata_id:
            return None
        
        image_url = await wikidata.get_artist_image_from_wikidata(wikidata_id)
        if not image_url:
            return None
        
        response = await client.get(image_url)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg")
            content = response.content
            
            asyncio.create_task(_write_cache(
                file_path,
                content,
                content_type,
                {"wikidata_id": wikidata_id}
            ))
            
            return (content, content_type, wikidata_id)
    
    except Exception as e:
        logger.error(f"Error fetching artist image for {artist_id}: {e}")
    
    return None


async def get_release_group_cover(
    release_group_id: str,
    size: Optional[str] = "500"
) -> Optional[tuple[bytes, str]]:
    """Get cover art for a release group.
    
    Args:
        release_group_id: MusicBrainz release group ID
        size: Image size ("250", "500", "1200", or None for original)
    
    Returns:
        Tuple of (image_data, content_type) or None
    """
    file_path = CACHE_DIR / f"rg_{release_group_id}_{size or 'orig'}.bin"
    
    if cached := await _read_cache(file_path):
        return cached
    
    size_suffix = f"-{size}" if size else ""
    front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front{size_suffix}"
    
    try:
        response = await client.get(front_url)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg")
            content = response.content
            
            asyncio.create_task(_write_cache(file_path, content, content_type))
            return (content, content_type)
    
    except Exception as e:
        logger.debug(f"Failed to fetch cover via release group: {e}")
    
    return await _get_cover_from_best_release(release_group_id, size, file_path)


async def _get_cover_from_best_release(
    release_group_id: str,
    size: Optional[str],
    cache_path: Path,
) -> Optional[tuple[bytes, str]]:
    """Fallback: get cover art from best release in group."""
    try:
        metadata_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}"
        response = await client.get(metadata_url, headers={"Accept": "application/json"})
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        release_url = data.get("release", "")
        if not release_url:
            return None
        
        release_id = release_url.split("/")[-1]
        
        size_suffix = f"-{size}" if size else ""
        release_front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
        
        response = await client.get(release_front_url)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg")
            content = response.content
            
            asyncio.create_task(_write_cache(cache_path, content, content_type))
            return (content, content_type)
    
    except Exception as e:
        logger.warning(f"Failed to fetch cover from best release: {e}")
    
    return None
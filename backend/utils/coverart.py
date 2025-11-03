import asyncio
import logging
import os
from typing import Optional

import aiofiles
import musicbrainzngs

from http_client import client
from utils.cache import get_cache
from utils import wikidata

log = logging.getLogger(__name__)
_cache = get_cache()

COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"
CACHE_DIR = "/app/cache/covers"

os.makedirs(CACHE_DIR, exist_ok=True)


async def get_artist_image(artist_id: str) -> Optional[tuple[bytes, str, str]]:
    fname = f"artist_{artist_id}.bin"
    fpath = os.path.join(CACHE_DIR, fname)
    meta_path = fpath + ".meta"
    wikidata_meta_path = fpath + ".wikidata_id"
    
    try:
        async with aiofiles.open(fpath, "rb") as f:
            data = await f.read()
        async with aiofiles.open(meta_path, "r") as m:
            content_type = (await m.read()).strip()
        async with aiofiles.open(wikidata_meta_path, "r") as w:
            wikidata_id = (await w.read()).strip()
        return (data, content_type, wikidata_id)
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning(f"Disk cache read error for artist {artist_id}: {exc}")
    
    cache_key = f"artist_wikidata:{artist_id}"
    cached_info = await _cache.get(cache_key)
    
    wikidata_url = None
    
    if cached_info:
        wikidata_url = cached_info
    else:
        try:
            artist_data = await asyncio.to_thread(
                musicbrainzngs.get_artist_by_id,
                artist_id,
                includes=["url-rels"]
            )
            
            if "artist" in artist_data:
                artist = artist_data["artist"]
                url_relations = artist.get("url-relation-list", [])
                
                for url_rel in url_relations:
                    if url_rel.get("type") == "wikidata":
                        wikidata_url = url_rel.get("target")
                        if wikidata_url:
                            break
            
            await _cache.set(cache_key, wikidata_url, ttl_seconds=86400)
            
        except musicbrainzngs.ResponseError:
            await _cache.set(cache_key, None, ttl_seconds=3600)
            return None
        except musicbrainzngs.NetworkError:
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
            
            asyncio.create_task(_write_artist_cache(fpath, meta_path, wikidata_meta_path, content, content_type, wikidata_id))
            
            return (content, content_type, wikidata_id)
    except Exception as exc:
        log.error(f"Error fetching artist image for {artist_id}: {exc}")
    
    return None


async def _write_artist_cache(fpath: str, meta_path: str, wikidata_meta_path: str, content: bytes, content_type: str, wikidata_id: str):
    """Write artist image to disk cache without blocking"""
    try:
        async with aiofiles.open(fpath, "wb") as f:
            await f.write(content)
        async with aiofiles.open(meta_path, "w") as m:
            await m.write(content_type)
        async with aiofiles.open(wikidata_meta_path, "w") as w:
            await w.write(wikidata_id)
    except Exception as exc:
        log.warning(f"Failed to write artist cache: {exc}")


async def get_release_group_cover(
    release_group_id: str,
    size: Optional[str] = "500"
) -> Optional[tuple[bytes, str]]:
    fname = f"rg_{release_group_id}_{size or 'orig'}.bin"
    fpath = os.path.join(CACHE_DIR, fname)
    meta_path = fpath + ".meta"
    
    try:
        async with aiofiles.open(fpath, "rb") as f:
            data = await f.read()
        async with aiofiles.open(meta_path, "r") as m:
            content_type = (await m.read()).strip()
        return (data, content_type)
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning(f"Disk cache read error for RG {release_group_id}: {exc}")
    
    if size:
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front-{size}"
    else:
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front"
    
    try:
        response = await client.get(front_url)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg")
            content = response.content
            
            asyncio.create_task(_write_cover_cache(fpath, meta_path, content, content_type))
            
            return (content, content_type)
    except Exception as exc:
        log.debug(f"Failed to fetch RG cover via CAA: {exc}")
    
    return await _get_cover_from_best_release(release_group_id, size)


async def _write_cover_cache(fpath: str, meta_path: str, content: bytes, content_type: str):
    try:
        async with aiofiles.open(fpath, "wb") as f:
            await f.write(content)
        async with aiofiles.open(meta_path, "w") as m:
            await m.write(content_type)
    except Exception as exc:
        log.warning(f"Failed to write cover cache: {exc}")


async def _get_cover_from_best_release(
    release_group_id: str,
    size: Optional[str]
) -> Optional[tuple[bytes, str]]:
    metadata_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}"
    
    fname = f"rg_{release_group_id}_{size or 'orig'}.bin"
    fpath = os.path.join(CACHE_DIR, fname)
    meta_path = fpath + ".meta"
    
    try:
        response = await client.get(metadata_url, headers={"Accept": "application/json"})
        if response.status_code == 200:
            data = response.json()
            release_url = data.get("release", "")
            if release_url:
                release_id = release_url.split("/")[-1]
                
                if size:
                    release_front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front-{size}"
                else:
                    release_front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front"
                
                response2 = await client.get(release_front_url)
                if response2.status_code == 200:
                    content_type = response2.headers.get("content-type", "image/jpeg")
                    content = response2.content
                    
                    asyncio.create_task(_write_cover_cache(fpath, meta_path, content, content_type))
                    
                    return (content, content_type)
    except Exception as exc:
        log.warning(f"Failed to fetch cover art metadata for {release_group_id}: {exc}")
    
    return None
    
    return None

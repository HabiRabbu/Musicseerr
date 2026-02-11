import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from urllib.parse import quote

import httpx

from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.queue.priority_queue import RequestPriority

if TYPE_CHECKING:
    from repositories.musicbrainz_repository import MusicBrainzRepository
    from repositories.lidarr import LidarrRepository

logger = logging.getLogger(__name__)


def _log_task_error(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logger.error(f"Background cache write failed: {task.exception()}")


def _is_valid_image_content_type(content_type: str) -> bool:
    if not content_type:
        return False
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in frozenset([
        "image/jpeg", "image/jpg", "image/png", "image/gif",
        "image/webp", "image/avif", "image/svg+xml",
    ])


class ArtistImageFetcher:
    def __init__(
        self,
        http_get_fn,
        write_cache_fn,
        cache: CacheInterface,
        mb_repo: Optional['MusicBrainzRepository'] = None,
        lidarr_repo: Optional['LidarrRepository'] = None
    ):
        self._http_get = http_get_fn
        self._write_disk_cache = write_cache_fn
        self._cache = cache
        self._mb_repo = mb_repo
        self._lidarr_repo = lidarr_repo

    async def fetch_artist_image(
        self,
        artist_id: str,
        size: Optional[int],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        logger.info(f"[IMG] Fetching artist image for {artist_id[:8]}... (size={size})")
        result = await self._fetch_from_lidarr(artist_id, size, file_path)
        if result:
            logger.info(f"[IMG] SUCCESS from Lidarr for {artist_id[:8]}...")
            return result
        logger.info(f"[IMG] Lidarr failed for {artist_id[:8]}..., trying Wikidata")
        result = await self._fetch_from_wikidata(artist_id, size, file_path)
        if result:
            logger.info(f"[IMG] SUCCESS from Wikidata for {artist_id[:8]}...")
            return result
        logger.info(f"[IMG] FAILED: No image found for {artist_id[:8]}... from any source")
        return None

    async def _fetch_from_lidarr(
        self,
        artist_id: str,
        size: Optional[int],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        if not self._lidarr_repo:
            logger.debug(f"[IMG:Lidarr] No Lidarr repo configured for {artist_id[:8]}")
            return None
        try:
            image_url = await self._lidarr_repo.get_artist_image_url(artist_id, size=size or 250)
            if not image_url:
                logger.info(f"[IMG:Lidarr] No image URL returned for {artist_id[:8]}")
                return None
            logger.info(f"[IMG:Lidarr] Fetching from URL for {artist_id[:8]}...")
            response = await self._http_get(image_url, RequestPriority.IMAGE_FETCH)
            if response.status_code != 200:
                logger.warning(f"[IMG:Lidarr] HTTP {response.status_code} for {artist_id[:8]}")
                return None
            content_type = response.headers.get("content-type", "")
            if not _is_valid_image_content_type(content_type):
                logger.warning(f"[IMG:Lidarr] Non-image content-type ({content_type}) for {artist_id[:8]}")
                return None
            content = response.content
            task = asyncio.create_task(self._write_disk_cache(file_path, content, content_type, {"source": "lidarr"}))
            task.add_done_callback(_log_task_error)
            return (content, content_type, "lidarr")
        except Exception as e:
            logger.warning(f"[IMG:Lidarr] Exception for {artist_id[:8]}: {e}")
            return None

    async def _fetch_from_wikidata(
        self,
        artist_id: str,
        size: Optional[int],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        cache_key = f"artist_wikidata:{artist_id}"
        wikidata_url = await self._cache.get(cache_key)
        if wikidata_url is None:
            wikidata_url = await self._lookup_wikidata_url(artist_id)
            ttl = 86400 if wikidata_url else 3600
            await self._cache.set(cache_key, wikidata_url, ttl_seconds=ttl)
        if not wikidata_url:
            return None
        try:
            match = re.search(r'/(?:wiki|entity)/(Q\d+)', wikidata_url)
            wikidata_id = match.group(1) if match else None
            if not wikidata_id:
                logger.debug(f"Could not parse Wikidata Q-id from URL: {wikidata_url}")
                return None
            api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await self._http_get(api_url, RequestPriority.IMAGE_FETCH)
            if response.status_code != 200:
                return None
            data = response.json()
            entity = data.get("entities", {}).get(wikidata_id, {})
            claims = entity.get("claims", {})
            image_claims = claims.get("P18", [])
            if not image_claims:
                return None
            filename = image_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
            if not filename:
                return None
            commons_api = (
                f"https://commons.wikimedia.org/w/api.php"
                f"?action=query&titles=File:{quote(filename)}"
                f"&prop=imageinfo&iiprop=url&format=json"
            )
            if size:
                commons_api += f"&iiurlwidth={size}"
            commons_response = await self._http_get(commons_api, RequestPriority.IMAGE_FETCH)
            if commons_response.status_code != 200:
                return None
            commons_data = commons_response.json()
            pages = commons_data.get("query", {}).get("pages", {})
            image_url = None
            for page in pages.values():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    if size and "thumburl" in imageinfo[0]:
                        image_url = imageinfo[0].get("thumburl")
                    else:
                        image_url = imageinfo[0].get("url")
                    break
            if not image_url:
                return None
            response = await self._http_get(image_url, RequestPriority.IMAGE_FETCH)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"[IMG:Wikidata] Non-image content-type ({content_type})")
                    return None
                content = response.content
                task = asyncio.create_task(self._write_disk_cache(file_path, content, content_type, {"wikidata_id": wikidata_id}))
                task.add_done_callback(_log_task_error)
                return (content, content_type, wikidata_id)
        except Exception as e:
            logger.error(f"Error fetching artist image for {artist_id}: {e}")
        return None

    async def _lookup_wikidata_url(self, artist_id: str) -> Optional[str]:
        logger.info(f"[IMG:Wikidata] Looking up wikidata URL for {artist_id[:8]}...")
        if not self._mb_repo:
            logger.warning(f"[IMG:Wikidata] MusicBrainz repository not available for {artist_id}")
            return None
        try:
            artist_data = await self._mb_repo.get_artist_relations(artist_id)
            if not artist_data:
                logger.info(f"[IMG:Wikidata] No artist data from MB for {artist_id[:8]}")
                return None
            url_relations = artist_data.get("relations", [])
            if url_relations:
                for url_rel in url_relations:
                    if isinstance(url_rel, dict):
                        typ = url_rel.get("type") or url_rel.get("link_type")
                        url_obj = url_rel.get("url", {})
                        target = url_obj.get("resource", "") if isinstance(url_obj, dict) else ""
                        if typ == "wikidata" and target:
                            logger.info(f"[IMG:Wikidata] Found URL for {artist_id[:8]}: {target}")
                            return target
            external_links = artist_data.get("external_links") or artist_data.get("external_links_list")
            if external_links:
                for ext in external_links:
                    try:
                        ext_type = getattr(ext, "type", None) if not isinstance(ext, dict) else ext.get("type")
                        ext_url = getattr(ext, "url", None) if not isinstance(ext, dict) else ext.get("url")
                    except Exception:
                        ext_type = None
                        ext_url = None
                    if ext_type == "wikidata" and ext_url:
                        return ext_url
            logger.info(f"[IMG:Wikidata] No wikidata link found for {artist_id[:8]}")
            return None
        except Exception as e:
            logger.error(f"[IMG:Wikidata] Failed to fetch artist metadata for {artist_id}: {e}")
            return None

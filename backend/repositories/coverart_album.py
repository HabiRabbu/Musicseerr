import asyncio
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from infrastructure.validators import validate_mbid
from infrastructure.queue.priority_queue import RequestPriority

if TYPE_CHECKING:
    from repositories.lidarr import LidarrRepository
    from repositories.musicbrainz_repository import MusicBrainzRepository
    from repositories.jellyfin_repository import JellyfinRepository

logger = logging.getLogger(__name__)


def _log_task_error(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logger.error(f"Background cache write failed: {task.exception()}")


COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"

VALID_IMAGE_CONTENT_TYPES = frozenset([
    "image/jpeg", "image/jpg", "image/png", "image/gif",
    "image/webp", "image/avif", "image/svg+xml",
])
LOCAL_SOURCE_TIMEOUT_SECONDS = 1.0


def _is_valid_image_content_type(content_type: str) -> bool:
    if not content_type:
        return False
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in VALID_IMAGE_CONTENT_TYPES


class AlbumCoverFetcher:
    def __init__(
        self,
        http_get_fn,
        write_cache_fn,
        lidarr_repo: Optional['LidarrRepository'] = None,
        mb_repo: Optional['MusicBrainzRepository'] = None,
        jellyfin_repo: Optional['JellyfinRepository'] = None,
    ):
        self._http_get = http_get_fn
        self._write_disk_cache = write_cache_fn
        self._lidarr_repo = lidarr_repo
        self._mb_repo = mb_repo
        self._jellyfin_repo = jellyfin_repo

    async def fetch_release_group_cover(
        self,
        release_group_id: str,
        size: Optional[str],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        size_int = int(size) if size and size.isdigit() else 500
        result = None
        try:
            result = await asyncio.wait_for(
                self._fetch_release_group_local_sources(release_group_id, file_path, size_int),
                timeout=LOCAL_SOURCE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.debug(f"Timed out local source lookup for release group {release_group_id[:8]}...")
        if result:
            return result
        size_suffix = f"-{size}" if size else ""
        front_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}/front{size_suffix}"
        try:
            response = await self._http_get(
                front_url,
                RequestPriority.IMAGE_FETCH,
                source="coverart",
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Non-image content-type from CoverArtArchive: {content_type}")
                else:
                    content = response.content
                    task = asyncio.create_task(
                        self._write_disk_cache(
                            file_path,
                            content,
                            content_type,
                            {"source": "cover-art-archive"},
                        )
                    )
                    task.add_done_callback(_log_task_error)
                    return (content, content_type, "cover-art-archive")
        except Exception as e:
            logger.debug(f"Failed to fetch cover via release group: {e}")
        return await self._get_cover_from_best_release(release_group_id, size, file_path)

    async def _fetch_release_group_local_sources(
        self,
        release_group_id: str,
        file_path: Path,
        size: int,
    ) -> Optional[tuple[bytes, str, str]]:
        result = await self._fetch_from_lidarr(release_group_id, file_path, size=size)
        if result:
            return result
        return await self._fetch_from_jellyfin(release_group_id, file_path)

    async def _get_cover_from_best_release(
        self,
        release_group_id: str,
        size: Optional[str],
        cache_path: Path,
    ) -> Optional[tuple[bytes, str, str]]:
        try:
            metadata_url = f"{COVER_ART_ARCHIVE_BASE}/release-group/{release_group_id}"
            response = await self._http_get(
                metadata_url,
                RequestPriority.IMAGE_FETCH,
                source="coverart",
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200:
                return None
            data = response.json()
            release_url = data.get("release", "")
            if not release_url:
                return None
            release_id = release_url.split("/")[-1]
            try:
                release_id = validate_mbid(release_id, "release")
            except ValueError as e:
                logger.warning(f"Invalid release MBID extracted from metadata: {e}")
                return None
            size_suffix = f"-{size}" if size else ""
            release_front_url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
            response = await self._http_get(
                release_front_url,
                RequestPriority.IMAGE_FETCH,
                source="coverart",
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Non-image content-type from release: {content_type}")
                    return None
                content = response.content
                task = asyncio.create_task(
                    self._write_disk_cache(
                        cache_path,
                        content,
                        content_type,
                        {"source": "cover-art-archive"},
                    )
                )
                task.add_done_callback(_log_task_error)
                return (content, content_type, "cover-art-archive")
        except Exception as e:
            logger.warning(f"Failed to fetch cover from best release: {e}")
        return None

    async def _fetch_from_lidarr(
        self,
        release_group_id: str,
        file_path: Path,
        size: Optional[int] = 500
    ) -> Optional[tuple[bytes, str, str]]:
        if not self._lidarr_repo:
            return None
        try:
            image_url = await self._lidarr_repo.get_album_image_url(release_group_id, size=size)
            if not image_url:
                return None
            logger.debug(f"Fetching album cover from Lidarr: {release_group_id[:8]}...")
            response = await self._http_get(
                image_url,
                RequestPriority.IMAGE_FETCH,
                source="lidarr",
            )
            if response.status_code != 200:
                return None
            content_type = response.headers.get("content-type", "")
            if not _is_valid_image_content_type(content_type):
                logger.warning(f"Non-image content-type from Lidarr album: {content_type}")
                return None
            content = response.content
            task = asyncio.create_task(self._write_disk_cache(file_path, content, content_type, {"source": "lidarr"}))
            task.add_done_callback(_log_task_error)
            return (content, content_type, "lidarr")
        except Exception as e:
            logger.debug(f"Failed to fetch album cover from Lidarr for {release_group_id}: {e}")
            return None

    async def _fetch_from_jellyfin(
        self,
        musicbrainz_id: str,
        file_path: Path,
    ) -> Optional[tuple[bytes, str, str]]:
        if not self._jellyfin_repo or not self._jellyfin_repo.is_configured():
            return None
        try:
            album = await self._jellyfin_repo.get_album_by_mbid(musicbrainz_id)
            if not album:
                return None
            image_url = self._jellyfin_repo.get_image_url(album.id, album.image_tag)
            if not image_url:
                return None
            response = await self._http_get(
                image_url,
                RequestPriority.IMAGE_FETCH,
                source="jellyfin",
                headers=self._jellyfin_repo.get_auth_headers(),
            )
            if response.status_code != 200:
                return None
            content_type = response.headers.get("content-type", "")
            if not _is_valid_image_content_type(content_type):
                logger.warning(f"Non-image content-type from Jellyfin album: {content_type}")
                return None
            content = response.content
            task = asyncio.create_task(
                self._write_disk_cache(file_path, content, content_type, {"source": "jellyfin"})
            )
            task.add_done_callback(_log_task_error)
            return (content, content_type, "jellyfin")
        except Exception as e:
            logger.debug(f"Failed to fetch album cover from Jellyfin for {musicbrainz_id}: {e}")
            return None

    async def fetch_release_cover(
        self,
        release_id: str,
        size: Optional[str],
        file_path: Path
    ) -> Optional[tuple[bytes, str, str]]:
        result = None
        try:
            result = await asyncio.wait_for(
                self._fetch_release_local_sources(release_id, file_path, size),
                timeout=LOCAL_SOURCE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.debug(f"Timed out local source lookup for release {release_id[:8]}...")
        if result:
            return result

        size_suffix = f"-{size}" if size else ""
        url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_id}/front{size_suffix}"
        try:
            response = await self._http_get(url, RequestPriority.IMAGE_FETCH)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if not _is_valid_image_content_type(content_type):
                    logger.warning(f"Non-image content-type from release cover: {content_type}")
                    return None
                content = response.content
                task = asyncio.create_task(
                    self._write_disk_cache(
                        file_path,
                        content,
                        content_type,
                        {"source": "cover-art-archive"},
                    )
                )
                task.add_done_callback(_log_task_error)
                return (content, content_type, "cover-art-archive")
        except Exception as e:
            logger.warning(f"Failed to fetch release cover for {release_id}: {e}")
        return None

    async def _fetch_release_local_sources(
        self,
        release_id: str,
        file_path: Path,
        size: Optional[str],
    ) -> Optional[tuple[bytes, str, str]]:
        size_int = int(size) if size and size.isdigit() else 500
        release_group_id = None
        if self._mb_repo:
            release_group_id = await self._mb_repo.get_release_group_id_from_release(release_id)

        if release_group_id:
            result = await self._fetch_from_lidarr(release_group_id, file_path, size=size_int)
            if result:
                return result
            result = await self._fetch_from_jellyfin(release_group_id, file_path)
            if result:
                return result

        return await self._fetch_from_jellyfin(release_id, file_path)

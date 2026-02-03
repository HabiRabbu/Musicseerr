import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)


def _log_task_error(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logger.error(f"Background task failed: {task.exception()}")


VALID_IMAGE_CONTENT_TYPES = frozenset([
    "image/jpeg", "image/jpg", "image/png", "image/gif",
    "image/webp", "image/avif", "image/svg+xml",
])


def is_valid_image_content_type(content_type: str) -> bool:
    if not content_type:
        return False
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in VALID_IMAGE_CONTENT_TYPES


def get_cache_filename(identifier: str, suffix: str = "") -> str:
    content = f"{identifier}:{suffix}"
    hash_digest = hashlib.sha1(content.encode()).hexdigest()
    return hash_digest


class CoverDiskCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def write(
        self,
        file_path: Path,
        content: bytes,
        content_type: str,
        extra_meta: Optional[dict[str, str]] = None,
        is_monitored: bool = False,
    ) -> None:
        try:
            now = datetime.now().timestamp()
            ttl = None if is_monitored else 24 * 3600
            meta = {
                'content_type': content_type,
                'created_at': now,
                'last_accessed': now,
                'size_bytes': len(content),
                'is_monitored': is_monitored
            }
            if ttl:
                meta['expires_at'] = now + ttl
            if extra_meta:
                meta.update(extra_meta)

            async def write_content():
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)

            async def write_meta():
                meta_path = file_path.with_suffix('.meta.json')
                async with aiofiles.open(meta_path, 'w') as f:
                    await f.write(json.dumps(meta))

            async def write_wikidata():
                if extra_meta and 'wikidata_url' in extra_meta:
                    wikidata_path = file_path.with_suffix('.wikidata')
                    async with aiofiles.open(wikidata_path, 'w') as f:
                        await f.write(extra_meta['wikidata_url'])

            await asyncio.gather(write_content(), write_meta(), write_wikidata())
        except Exception as e:
            logger.warning(f"Failed to write disk cache: {e}")

    async def read(
        self,
        file_path: Path,
        extra_keys: Optional[list[str]] = None
    ) -> Optional[tuple[bytes, str, Optional[dict]]]:
        if not file_path.exists():
            return None
        try:
            async def read_content():
                async with aiofiles.open(file_path, 'rb') as f:
                    return await f.read()

            async def read_meta():
                meta_path = file_path.with_suffix('.meta.json')
                if meta_path.exists():
                    async with aiofiles.open(meta_path, 'r') as f:
                        return json.loads(await f.read())
                return None

            content, meta = await asyncio.gather(read_content(), read_meta())
            if not content:
                return None
            content_type = 'image/jpeg'
            extra_data = {}
            if meta:
                content_type = meta.get('content_type', content_type)
                if 'expires_at' in meta:
                    now = datetime.now().timestamp()
                    if now > meta['expires_at'] and not meta.get('is_monitored', False):
                        file_path.unlink(missing_ok=True)
                        file_path.with_suffix('.meta.json').unlink(missing_ok=True)
                        return None
                if extra_keys:
                    async def read_extra_key(key: str):
                        ext_path = file_path.with_suffix(f'.{key}')
                        if ext_path.exists():
                            async with aiofiles.open(ext_path, 'r') as f:
                                return key, await f.read()
                        return key, None
                    results = await asyncio.gather(*[read_extra_key(k) for k in extra_keys])
                    for k, v in results:
                        if v is not None:
                            extra_data[k] = v
            task = asyncio.create_task(self._update_meta_access(file_path.with_suffix('.meta.json'), meta))
            task.add_done_callback(_log_task_error)
            return content, content_type, extra_data if extra_data else None
        except Exception as e:
            logger.warning(f"Failed to read disk cache: {e}")
            return None

    async def _update_meta_access(self, meta_file: Path, meta: dict) -> None:
        if meta is None or not meta_file.exists():
            return
        try:
            meta['last_accessed'] = datetime.now().timestamp()
            async with aiofiles.open(meta_file, 'w') as f:
                await f.write(json.dumps(meta))
        except Exception:
            pass

    def get_file_path(self, identifier: str, suffix: str) -> Path:
        cache_filename = get_cache_filename(identifier, suffix)
        return self.cache_dir / f"{cache_filename}.bin"

    async def promote_to_persistent(self, identifier: str, identifier_type: str = "album") -> bool:
        try:
            if identifier_type == "album":
                prefixes = ["rg_"]
                sizes = ["250", "500"]
            else:
                prefixes = ["artist_"]
                sizes = ["250", "500"]
            for prefix in prefixes:
                for size in sizes:
                    full_id = f"{prefix}{identifier}" if prefix == "artist_" else f"{prefix}{identifier}"
                    if prefix == "artist_":
                        full_id = f"artist_{identifier}_{size}"
                        suffix = "img"
                    else:
                        suffix = size
                    cache_filename = get_cache_filename(full_id, suffix)
                    file_path = self.cache_dir / f"{cache_filename}.bin"
                    meta_path = file_path.with_suffix('.meta.json')
                    if file_path.exists() and meta_path.exists():
                        async with aiofiles.open(meta_path, 'r') as f:
                            meta = json.loads(await f.read())
                        if not meta.get('is_monitored', False):
                            meta['is_monitored'] = True
                            meta.pop('expires_at', None)
                            async with aiofiles.open(meta_path, 'w') as f:
                                await f.write(json.dumps(meta))
                            logger.debug(f"Promoted cover cache to persistent: {identifier_type}={identifier}, size={size}")
            return True
        except Exception as e:
            logger.warning(f"Failed to promote cover cache to persistent: {e}")
            return False

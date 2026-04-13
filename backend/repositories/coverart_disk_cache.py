import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiofiles
import msgspec

logger = logging.getLogger(__name__)


def _encode_json(data: object) -> str:
    return msgspec.json.encode(data).decode("utf-8")


def _decode_json(text: str) -> dict[str, Any]:
    return msgspec.json.decode(text.encode("utf-8"), type=dict[str, Any])


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
    def __init__(
        self,
        cache_dir: Path,
        max_size_mb: Optional[int] = None,
        eviction_check_interval_seconds: int = 60,
        non_monitored_ttl_seconds: int = 86400,
    ):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024 if max_size_mb and max_size_mb > 0 else None
        self._eviction_check_interval_seconds = max(eviction_check_interval_seconds, 1)
        self._non_monitored_ttl_seconds = max(non_monitored_ttl_seconds, 1)
        self._last_eviction_check = 0.0
        self._eviction_lock = asyncio.Lock()

    async def write(
        self,
        file_path: Path,
        content: bytes,
        content_type: str,
        extra_meta: Optional[dict[str, object]] = None,
        is_monitored: bool = False,
    ) -> None:
        try:
            now = datetime.now().timestamp()
            ttl = None if is_monitored else self._non_monitored_ttl_seconds
            content_sha1 = hashlib.sha1(content).hexdigest()
            meta = {
                'content_type': content_type,
                'created_at': now,
                'last_accessed': now,
                'size_bytes': len(content),
                'is_monitored': is_monitored,
                'content_sha1': content_sha1,
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
                    await f.write(_encode_json(meta))

            async def write_wikidata():
                if extra_meta and 'wikidata_url' in extra_meta:
                    wikidata_path = file_path.with_suffix('.wikidata')
                    async with aiofiles.open(wikidata_path, 'w') as f:
                        await f.write(str(extra_meta['wikidata_url']))

            await asyncio.gather(write_content(), write_meta(), write_wikidata())
            await self.enforce_size_limit()
        except Exception:  # noqa: BLE001
            pass

    async def write_negative(
        self,
        file_path: Path,
        ttl_seconds: int = 4 * 3600,
    ) -> None:
        try:
            now = datetime.now().timestamp()
            meta = {
                "created_at": now,
                "last_accessed": now,
                "expires_at": now + ttl_seconds,
                "negative": True,
                "is_monitored": False,
            }
            meta_path = file_path.with_suffix(".meta.json")
            async with aiofiles.open(meta_path, "w") as f:
                await f.write(_encode_json(meta))
        except Exception:  # noqa: BLE001
            pass

    async def is_negative(self, file_path: Path) -> bool:
        meta_path = file_path.with_suffix(".meta.json")
        if not meta_path.exists():
            return False
        try:
            async with aiofiles.open(meta_path, "r") as f:
                meta = _decode_json(await f.read())

            if not meta.get("negative", False):
                return False

            expires_at = meta.get("expires_at")
            if expires_at is None:
                return False

            now = datetime.now().timestamp()
            if now > expires_at:
                meta_path.unlink(missing_ok=True)
                return False

            task = asyncio.create_task(self._update_meta_access(meta_path, meta))
            task.add_done_callback(_log_task_error)
            return True
        except Exception:  # noqa: BLE001
            return False

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
                        return _decode_json(await f.read())
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
                        if key in meta:
                            return key, meta.get(key)
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
        except Exception:  # noqa: BLE001
            return None

    async def _update_meta_access(self, meta_file: Path, meta: dict) -> None:
        if meta is None or not meta_file.exists():
            return
        try:
            meta['last_accessed'] = datetime.now().timestamp()
            async with aiofiles.open(meta_file, 'w') as f:
                await f.write(_encode_json(meta))
        except OSError:
            pass

    async def get_content_hash(self, file_path: Path) -> Optional[str]:
        meta_path = file_path.with_suffix('.meta.json')
        if not meta_path.exists():
            return None

        try:
            async with aiofiles.open(meta_path, 'r') as f:
                meta = _decode_json(await f.read())

            if 'expires_at' in meta and not meta.get('is_monitored', False):
                now = datetime.now().timestamp()
                if now > meta['expires_at']:
                    file_path.unlink(missing_ok=True)
                    meta_path.unlink(missing_ok=True)
                    file_path.with_suffix('.wikidata').unlink(missing_ok=True)
                    return None

            content_hash = meta.get('content_sha1')
            if content_hash:
                task = asyncio.create_task(self._update_meta_access(meta_path, meta))
                task.add_done_callback(_log_task_error)
                return str(content_hash)

            if not file_path.exists():
                return None

            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()

            if not content:
                return None

            content_hash = hashlib.sha1(content).hexdigest()
            meta['content_sha1'] = content_hash
            await self._update_meta_access(meta_path, meta)
            return content_hash
        except Exception:  # noqa: BLE001
            return None

    async def enforce_size_limit(self, force: bool = False) -> int:
        if self.max_size_bytes is None:
            return 0

        now = datetime.now().timestamp()
        if not force and (now - self._last_eviction_check) < self._eviction_check_interval_seconds:
            return 0

        async with self._eviction_lock:
            now = datetime.now().timestamp()
            if not force and (now - self._last_eviction_check) < self._eviction_check_interval_seconds:
                return 0

            self._last_eviction_check = now

            total_bytes = 0
            candidates: list[tuple[float, Path, int]] = []

            for file_path in self.cache_dir.glob('*.bin'):
                try:
                    size_bytes = file_path.stat().st_size
                except FileNotFoundError:
                    continue

                total_bytes += size_bytes

                meta_path = file_path.with_suffix('.meta.json')
                meta: dict = {}
                if meta_path.exists():
                    try:
                        async with aiofiles.open(meta_path, 'r') as f:
                            meta = _decode_json(await f.read())
                    except Exception:  # noqa: BLE001
                        meta = {}

                if meta.get('is_monitored', False):
                    continue

                last_accessed = float(meta.get('last_accessed', meta.get('created_at', 0.0)) or 0.0)
                candidates.append((last_accessed, file_path, size_bytes))

            if total_bytes <= self.max_size_bytes:
                return 0

            bytes_to_free = total_bytes - self.max_size_bytes
            bytes_freed = 0

            candidates.sort(key=lambda item: item[0])

            for _, file_path, size_bytes in candidates:
                file_path.unlink(missing_ok=True)
                file_path.with_suffix('.meta.json').unlink(missing_ok=True)
                file_path.with_suffix('.wikidata').unlink(missing_ok=True)
                bytes_freed += size_bytes

                if bytes_freed >= bytes_to_free:
                    break

            return bytes_freed

    async def delete_by_identifiers(self, identifiers: list[tuple[str, str]]) -> int:
        count = 0
        for identifier, suffix in identifiers:
            cache_filename = get_cache_filename(identifier, suffix)
            bin_path = self.cache_dir / f"{cache_filename}.bin"
            existed = bin_path.exists()
            bin_path.unlink(missing_ok=True)
            (self.cache_dir / f"{cache_filename}.meta.json").unlink(missing_ok=True)
            (self.cache_dir / f"{cache_filename}.wikidata").unlink(missing_ok=True)
            if existed:
                count += 1
        return count

    def cleanup_expired(self) -> int:
        """Synchronous helper for background tasks via asyncio.to_thread()."""
        count = 0
        now = datetime.now().timestamp()
        if not self.cache_dir.exists():
            return 0
        for meta_path in self.cache_dir.glob("*.meta.json"):
            try:
                meta = _decode_json(meta_path.read_text())
            except Exception:  # noqa: BLE001
                continue
            if not meta.get("is_monitored", False) and "expires_at" in meta and meta["expires_at"] < now:
                stem = meta_path.name.removesuffix(".meta.json")
                (self.cache_dir / f"{stem}.bin").unlink(missing_ok=True)
                meta_path.unlink(missing_ok=True)
                (self.cache_dir / f"{stem}.wikidata").unlink(missing_ok=True)
                count += 1
        return count

    def demote_orphaned(self, valid_hashes: set[str]) -> int:
        """Synchronous helper for background tasks via asyncio.to_thread()."""
        count = 0
        now = datetime.now().timestamp()
        if not self.cache_dir.exists():
            return 0
        for meta_path in self.cache_dir.glob("*.meta.json"):
            try:
                meta = _decode_json(meta_path.read_text())
            except Exception:  # noqa: BLE001
                continue
            if not meta.get("is_monitored", False):
                continue
            stem = meta_path.name.removesuffix(".meta.json")
            if stem in valid_hashes:
                continue
            meta["is_monitored"] = False
            meta["expires_at"] = now + 48 * 3600
            try:
                meta_path.write_text(_encode_json(meta))
            except Exception:  # noqa: BLE001
                continue
            count += 1
        return count

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
                            meta = _decode_json(await f.read())
                        if not meta.get('is_monitored', False):
                            meta['is_monitored'] = True
                            meta.pop('expires_at', None)
                            async with aiofiles.open(meta_path, 'w') as f:
                                await f.write(_encode_json(meta))
            return True
        except Exception:  # noqa: BLE001
            return False

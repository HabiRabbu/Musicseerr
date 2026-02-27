import asyncio
import hashlib

import pytest

from repositories.coverart_disk_cache import CoverDiskCache


@pytest.mark.asyncio
async def test_write_persists_content_hash(tmp_path):
    cache = CoverDiskCache(tmp_path)
    file_path = cache.get_file_path("rg_test", "500")
    content = b"image-bytes-1"

    await cache.write(file_path, content, "image/jpeg", {"source": "cover-art-archive"})

    content_hash = await cache.get_content_hash(file_path)
    assert content_hash == hashlib.sha1(content).hexdigest()


@pytest.mark.asyncio
async def test_enforce_size_limit_evicts_oldest_non_monitored(tmp_path):
    cache = CoverDiskCache(tmp_path, max_size_mb=1)

    first_path = cache.get_file_path("rg_first", "500")
    second_path = cache.get_file_path("rg_second", "500")

    content = b"a" * (700 * 1024)

    await cache.write(first_path, content, "image/jpeg", {"source": "cover-art-archive"})
    await asyncio.sleep(0.02)
    await cache.write(second_path, content, "image/jpeg", {"source": "cover-art-archive"})

    await cache.enforce_size_limit(force=True)

    assert not first_path.exists()
    assert second_path.exists()


@pytest.mark.asyncio
async def test_enforce_size_limit_preserves_monitored_entries(tmp_path):
    cache = CoverDiskCache(tmp_path, max_size_mb=1)

    monitored_path = cache.get_file_path("rg_monitored", "500")
    transient_path = cache.get_file_path("rg_transient", "500")

    await cache.write(monitored_path, b"m" * (800 * 1024), "image/jpeg", is_monitored=True)
    await cache.write(transient_path, b"t" * (400 * 1024), "image/jpeg")

    await cache.enforce_size_limit(force=True)

    assert monitored_path.exists()
    assert not transient_path.exists()

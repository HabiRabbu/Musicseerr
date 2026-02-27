import hashlib
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from repositories.coverart_repository import CoverArtRepository


RELEASE_GROUP_MBID = '11111111-1111-1111-1111-111111111111'
RELEASE_MBID = '22222222-2222-2222-2222-222222222222'


@pytest.mark.asyncio
async def test_release_group_disk_hit_is_promoted_to_memory_and_skips_second_disk_read(tmp_path):
    async with httpx.AsyncClient() as http_client:
        cache = MagicMock()
        repo = CoverArtRepository(http_client=http_client, cache=cache, cache_dir=tmp_path)

        repo._disk_cache.read = AsyncMock(
            return_value=(b'disk-image', 'image/jpeg', {'source': 'cover-art-archive'})
        )
        repo._disk_cache.is_negative = AsyncMock(return_value=False)

        first = await repo.get_release_group_cover(RELEASE_GROUP_MBID, size='500')
        second = await repo.get_release_group_cover(RELEASE_GROUP_MBID, size='500')

        assert first == second == (b'disk-image', 'image/jpeg', 'cover-art-archive')
        assert repo._disk_cache.read.await_count == 1


@pytest.mark.asyncio
async def test_release_cover_etag_uses_memory_before_disk(tmp_path):
    async with httpx.AsyncClient() as http_client:
        cache = MagicMock()
        repo = CoverArtRepository(http_client=http_client, cache=cache, cache_dir=tmp_path)

        identifier = f'rel_{RELEASE_MBID}'
        suffix = '500'
        cache_key = repo._memory_cache_key(identifier, suffix)

        await repo._cover_memory_cache.set(cache_key, b'cached-image', 'image/jpeg', 'cover-art-archive')
        repo._disk_cache.get_content_hash = AsyncMock(return_value='disk-hash')

        etag = await repo.get_release_cover_etag(RELEASE_MBID, size=suffix)

        assert etag == hashlib.sha1(b'cached-image').hexdigest()
        repo._disk_cache.get_content_hash.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_image_payload_is_not_stored_in_memory_cache(tmp_path):
    async with httpx.AsyncClient() as http_client:
        cache = MagicMock()
        repo = CoverArtRepository(http_client=http_client, cache=cache, cache_dir=tmp_path)

        repo._disk_cache.read = AsyncMock(return_value=(b'not-image', 'text/plain', {'source': 'disk'}))
        repo._disk_cache.is_negative = AsyncMock(return_value=False)

        first = await repo.get_release_cover(RELEASE_MBID, size='500')
        second = await repo.get_release_cover(RELEASE_MBID, size='500')

        assert first == second == (b'not-image', 'text/plain', 'disk')
        assert repo._disk_cache.read.await_count == 2

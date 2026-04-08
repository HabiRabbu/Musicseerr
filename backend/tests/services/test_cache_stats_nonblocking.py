import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.cache_service import CacheService


def _make_service() -> CacheService:
    cache = MagicMock()
    cache.size.return_value = 10
    cache.estimate_memory_bytes.return_value = 1024
    lib_cache = AsyncMock()
    lib_cache.get_stats = AsyncMock(return_value={
        "db_size_bytes": 0,
        "artist_count": 0,
        "album_count": 0,
    })
    disk_cache = MagicMock()
    disk_cache.get_stats.return_value = {
        "total_count": 0,
        "album_count": 0,
        "artist_count": 0,
        "audiodb_artist_count": 0,
        "audiodb_album_count": 0,
    }
    return CacheService(cache=cache, library_db=lib_cache, disk_cache=disk_cache)


class TestCacheStatsNonblocking:
    @pytest.mark.asyncio
    async def test_get_stats_uses_to_thread(self):
        """subprocess.run calls should be wrapped with asyncio.to_thread."""
        svc = _make_service()

        fake_du = MagicMock()
        fake_du.returncode = 0
        fake_du.stdout = "12345\t/app/cache/covers"

        fake_find = MagicMock()
        fake_find.returncode = 0
        fake_find.stdout = "file1.jpg\nfile2.jpg"

        call_count = 0

        async def mock_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fake_du
            return fake_find

        with patch("services.cache_service.get_covers_cache_dir") as mock_get_dir, \
             patch("services.cache_service.shutil.which", return_value="/usr/bin/du"), \
             patch("services.cache_service.asyncio.to_thread", side_effect=mock_to_thread) as mock_tt:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_dir.__str__ = lambda s: "/app/cache/covers"
            mock_get_dir.return_value = mock_dir

            stats = await svc.get_stats()

            assert mock_tt.call_count == 2
            assert stats.disk_cover_count == 2
            assert stats.disk_cover_size_bytes == 12345

    @pytest.mark.asyncio
    async def test_get_stats_cached_response(self):
        """Second call within TTL returns cached stats without subprocess."""
        svc = _make_service()

        with patch("services.cache_service.get_covers_cache_dir") as mock_get_dir:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            mock_get_dir.return_value = mock_dir

            stats1 = await svc.get_stats()
            stats2 = await svc.get_stats()

            assert stats1 is stats2

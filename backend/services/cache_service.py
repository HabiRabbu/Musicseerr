import asyncio
import logging
from pathlib import Path

from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cache.disk_cache import DiskMetadataCache
from api.v1.schemas.cache import CacheStats, CacheClearResponse

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/app/cache/covers")


class CacheService:
    
    def __init__(self, cache: CacheInterface, library_cache: LibraryCache, disk_cache: DiskMetadataCache):
        self._cache = cache
        self._library_cache = library_cache
        self._disk_cache = disk_cache
        self._cached_stats: CacheStats | None = None
        self._stats_cache_time: float = 0.0
        self._stats_cache_ttl: float = 30.0
        self._stats_lock = asyncio.Lock()
    
    async def get_stats(self) -> CacheStats:
        import time
        import subprocess
        import shutil
        
        async with self._stats_lock:
            now = time.time()
            if self._cached_stats and (now - self._stats_cache_time) < self._stats_cache_ttl:
                return self._cached_stats
            
            memory_entries = self._cache.size()
            memory_bytes = self._cache.estimate_memory_bytes()
            memory_mb = memory_bytes / (1024 * 1024)
            
            metadata_stats = self._disk_cache.get_stats()
            metadata_count = metadata_stats['total_count']
            metadata_albums = metadata_stats['album_count']
            metadata_artists = metadata_stats['artist_count']
            
            disk_count = 0
            disk_bytes = 0
            
            if CACHE_DIR.exists():
                du_available = shutil.which('du') is not None
                if du_available:
                    try:
                        result = subprocess.run(
                            ['du', '-sb', str(CACHE_DIR)],
                            capture_output=True,
                            text=True,
                            timeout=5.0
                        )
                        if result.returncode == 0:
                            disk_bytes = int(result.stdout.split()[0])
                            result = subprocess.run(
                                ['find', str(CACHE_DIR), '-type', 'f'],
                                capture_output=True,
                                text=True,
                                timeout=5.0
                            )
                            if result.returncode == 0:
                                disk_count = len(result.stdout.strip().split('\n'))
                                logger.debug(f"Disk cache stats calculated via subprocess: {disk_count} files, {disk_bytes} bytes")
                        else:
                            du_available = False
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError) as e:
                        logger.warning(f"Subprocess disk stats failed, falling back to Python: {e}")
                        du_available = False
                
                if not du_available:
                    for file_path in CACHE_DIR.rglob("*"):
                        if file_path.is_file():
                            disk_count += 1
                            disk_bytes += file_path.stat().st_size
            
            disk_mb = disk_bytes / (1024 * 1024)
            
            lib_stats = await self._library_cache.get_stats()
            lib_bytes = lib_stats['db_size_bytes']
            lib_mb = lib_bytes / (1024 * 1024)
            
            total_bytes = memory_bytes + disk_bytes + lib_bytes
            total_mb = total_bytes / (1024 * 1024)
            
            stats = CacheStats(
                memory_entries=memory_entries,
                memory_size_bytes=memory_bytes,
                memory_size_mb=round(memory_mb, 2),
                disk_metadata_count=metadata_count,
                disk_metadata_albums=metadata_albums,
                disk_metadata_artists=metadata_artists,
                disk_cover_count=disk_count,
                disk_cover_size_bytes=disk_bytes,
                disk_cover_size_mb=round(disk_mb, 2),
                library_db_artist_count=lib_stats['artist_count'],
                library_db_album_count=lib_stats['album_count'],
                library_db_size_bytes=lib_bytes,
                library_db_size_mb=round(lib_mb, 2),
                library_db_last_sync=lib_stats.get('last_sync'),
                total_size_bytes=total_bytes,
                total_size_mb=round(total_mb, 2)
            )
            
            self._cached_stats = stats
            self._stats_cache_time = now
            
            return stats
    
    async def clear_memory_cache(self) -> CacheClearResponse:
        try:
            entries_before = self._cache.size()
            await self._cache.clear()
            
            self._cached_stats = None
            
            logger.info(f"Cleared {entries_before} memory cache entries")
            
            return CacheClearResponse(
                success=True,
                message=f"Successfully cleared {entries_before} memory cache entries",
                cleared_memory_entries=entries_before,
                cleared_disk_files=0
            )
        except Exception as e:
            logger.error(f"Failed to clear memory cache: {e}")
            return CacheClearResponse(
                success=False,
                message=f"Failed to clear memory cache: {str(e)}",
                cleared_memory_entries=0,
                cleared_disk_files=0
            )
    
    async def clear_disk_cache(self) -> CacheClearResponse:
        try:
            metadata_stats = self._disk_cache.get_stats()
            metadata_count = metadata_stats['total_count']
            await self._disk_cache.clear_all()
            
            files_cleared = 0
            if CACHE_DIR.exists():
                for file_path in CACHE_DIR.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        files_cleared += 1
                
                logger.info(f"Cleared {metadata_count} metadata files and {files_cleared} cover image files from disk")
            
            self._cached_stats = None
            
            return CacheClearResponse(
                success=True,
                message=f"Successfully cleared {metadata_count} metadata files and {files_cleared} cover images from disk",
                cleared_memory_entries=0,
                cleared_disk_files=files_cleared + metadata_count
            )
        except Exception as e:
            logger.error(f"Failed to clear disk cache: {e}")
            return CacheClearResponse(
                success=False,
                message=f"Failed to clear disk cache: {str(e)}",
                cleared_memory_entries=0,
                cleared_disk_files=0
            )
    
    async def clear_all_cache(self) -> CacheClearResponse:
        try:
            memory_entries = self._cache.size()
            await self._cache.clear()
            
            metadata_stats = self._disk_cache.get_stats()
            metadata_count = metadata_stats['total_count']
            await self._disk_cache.clear_all()
            
            disk_files = 0
            if CACHE_DIR.exists():
                for file_path in CACHE_DIR.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        disk_files += 1
            
            self._cached_stats = None
            
            logger.info(f"Cleared all cache: {memory_entries} memory entries, {metadata_count} metadata files, {disk_files} cover files (library DB preserved)")
            
            return CacheClearResponse(
                success=True,
                message=f"Successfully cleared {memory_entries} memory entries, {metadata_count} metadata files, and {disk_files} cover files (library database preserved)",
                cleared_memory_entries=memory_entries,
                cleared_disk_files=disk_files + metadata_count
            )
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return CacheClearResponse(
                success=False,
                message=f"Failed to clear cache: {str(e)}",
                cleared_memory_entries=0,
                cleared_disk_files=0
            )
    
    async def clear_library_cache(self) -> CacheClearResponse:
        try:
            lib_stats = await self._library_cache.get_stats()
            artists_before = lib_stats['artist_count']
            albums_before = lib_stats['album_count']
            
            await self._library_cache.clear()
            
            self._cached_stats = None
            
            logger.info(f"Cleared library cache: {artists_before} artists, {albums_before} albums")
            
            return CacheClearResponse(
                success=True,
                message=f"Successfully cleared library database: {artists_before} artists, {albums_before} albums",
                cleared_memory_entries=0,
                cleared_disk_files=0,
                cleared_library_artists=artists_before,
                cleared_library_albums=albums_before
            )
        except Exception as e:
            logger.error(f"Failed to clear library cache: {e}")
            return CacheClearResponse(
                success=False,
                message=f"Failed to clear library cache: {str(e)}",
                cleared_memory_entries=0,
                cleared_disk_files=0
            )

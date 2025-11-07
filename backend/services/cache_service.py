"""Service for cache management operations."""
import logging
from pathlib import Path

from infrastructure.cache.memory_cache import CacheInterface
from api.v1.schemas.cache import CacheStats, CacheClearResponse

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/app/cache/covers")


class CacheService:
    """Service for managing cache operations."""
    
    def __init__(self, cache: CacheInterface):
        self._cache = cache
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics including memory and disk usage."""
        # Memory cache stats
        memory_entries = self._cache.size()
        memory_bytes = self._cache.estimate_memory_bytes()
        memory_mb = memory_bytes / (1024 * 1024)
        
        # Disk cache stats
        disk_count = 0
        disk_bytes = 0
        
        if CACHE_DIR.exists():
            for file_path in CACHE_DIR.rglob("*"):
                if file_path.is_file():
                    disk_count += 1
                    disk_bytes += file_path.stat().st_size
        
        disk_mb = disk_bytes / (1024 * 1024)
        
        # Total
        total_bytes = memory_bytes + disk_bytes
        total_mb = total_bytes / (1024 * 1024)
        
        return CacheStats(
            memory_entries=memory_entries,
            memory_size_bytes=memory_bytes,
            memory_size_mb=round(memory_mb, 2),
            disk_cover_count=disk_count,
            disk_cover_size_bytes=disk_bytes,
            disk_cover_size_mb=round(disk_mb, 2),
            total_size_bytes=total_bytes,
            total_size_mb=round(total_mb, 2)
        )
    
    async def clear_memory_cache(self) -> CacheClearResponse:
        """Clear all memory cache entries."""
        try:
            entries_before = self._cache.size()
            await self._cache.clear()
            
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
        """Clear all disk cache (cover images)."""
        try:
            files_cleared = 0
            
            if CACHE_DIR.exists():
                for file_path in CACHE_DIR.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        files_cleared += 1
                
                logger.info(f"Cleared {files_cleared} cover image files from disk")
            
            return CacheClearResponse(
                success=True,
                message=f"Successfully cleared {files_cleared} cover images from disk",
                cleared_memory_entries=0,
                cleared_disk_files=files_cleared
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
        """Clear both memory and disk cache."""
        try:
            # Clear memory cache
            memory_entries = self._cache.size()
            await self._cache.clear()
            
            # Clear disk cache
            disk_files = 0
            if CACHE_DIR.exists():
                for file_path in CACHE_DIR.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        disk_files += 1
            
            logger.info(f"Cleared all cache: {memory_entries} memory entries, {disk_files} disk files")
            
            return CacheClearResponse(
                success=True,
                message=f"Successfully cleared {memory_entries} memory entries and {disk_files} disk files",
                cleared_memory_entries=memory_entries,
                cleared_disk_files=disk_files
            )
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return CacheClearResponse(
                success=False,
                message=f"Failed to clear cache: {str(e)}",
                cleared_memory_entries=0,
                cleared_disk_files=0
            )

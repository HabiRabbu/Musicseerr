"""Cache management endpoints."""
import logging
from fastapi import APIRouter, HTTPException

from api.v1.schemas.cache import CacheStats, CacheClearResponse
from core.dependencies import get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/stats", response_model=CacheStats)
async def get_cache_stats():
    """Get cache statistics including memory and disk usage."""
    try:
        cache_service = get_cache_service()
        return cache_service.get_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {e}")


@router.post("/clear/memory", response_model=CacheClearResponse)
async def clear_memory_cache():
    """Clear all memory cache entries."""
    try:
        cache_service = get_cache_service()
        result = await cache_service.clear_memory_cache()
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear memory cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear memory cache: {e}")


@router.post("/clear/disk", response_model=CacheClearResponse)
async def clear_disk_cache():
    """Clear all disk cache (cover images)."""
    try:
        cache_service = get_cache_service()
        result = await cache_service.clear_disk_cache()
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear disk cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear disk cache: {e}")


@router.post("/clear/all", response_model=CacheClearResponse)
async def clear_all_cache():
    """Clear both memory and disk cache."""
    try:
        cache_service = get_cache_service()
        result = await cache_service.clear_all_cache()
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear all cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear all cache: {e}")

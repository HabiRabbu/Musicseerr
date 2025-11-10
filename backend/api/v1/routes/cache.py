import logging
from fastapi import APIRouter, HTTPException

from api.v1.schemas.cache import CacheStats, CacheClearResponse
from core.dependencies import get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/stats", response_model=CacheStats)
async def get_cache_stats():
    try:
        cache_service = get_cache_service()
        return await cache_service.get_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {e}")


@router.post("/clear/memory", response_model=CacheClearResponse)
async def clear_memory_cache():
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


@router.post("/clear/library", response_model=CacheClearResponse)
async def clear_library_cache():
    try:
        cache_service = get_cache_service()
        result = await cache_service.clear_library_cache()
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear library cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear library cache: {e}")

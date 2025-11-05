import logging
from fastapi import APIRouter, HTTPException
from api.v1.schemas.settings import UserPreferences
from core.dependencies import get_preferences_service, get_cache
from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_preferences()
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {e}")


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(preferences: UserPreferences):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_preferences(preferences)
        
        cache = get_cache()
        cleared_artist = await cache.clear_prefix("artist:")
        cleared_mb_artist = await cache.clear_prefix("mb_artist_detail:")
        cleared_mb_artists = await cache.clear_prefix("mb_artists:")
        cleared_mb_albums = await cache.clear_prefix("mb_albums:")
        
        total_cleared = cleared_artist + cleared_mb_artist + cleared_mb_artists + cleared_mb_albums
        logger.info(f"Updated user preferences. Cleared {total_cleared} cache entries.")
        
        return preferences
    except ConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save preferences: {e}")

"""Settings endpoints for user preferences."""
import logging

from fastapi import APIRouter, HTTPException

from models import UserPreferences
from config_manager import get_user_preferences, save_user_preferences
from utils.cache import clear_cache_prefix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences():
    """Get user preferences for release filtering.
    
    Returns current user preferences. When authentication is added,
    this will return user-specific preferences.
    """
    try:
        prefs = get_user_preferences()
        return UserPreferences(**prefs)
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {e}")


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(preferences: UserPreferences):
    """Update user preferences for release filtering.
    
    Currently saves globally. When authentication is added,
    this will save per-user preferences.
    """
    try:
        prefs_dict = preferences.model_dump()
        
        save_user_preferences(prefs_dict)
        
        cleared_artist = await clear_cache_prefix("artist:")
        cleared_mb_artist = await clear_cache_prefix("mb_artist_detail:")
        cleared_mb_artists = await clear_cache_prefix("mb_artists:")
        cleared_mb_albums = await clear_cache_prefix("mb_albums:")
        
        logger.info(
            f"Updated user preferences: {prefs_dict}. "
            f"Cleared {cleared_artist + cleared_mb_artist + cleared_mb_artists + cleared_mb_albums} cache entries."
        )
        
        return preferences
    except Exception as e:
        logger.error(f"Failed to save preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save preferences: {e}")

import logging
from fastapi import APIRouter, HTTPException
from api.v1.schemas.settings import UserPreferences, LidarrSettings
from api.v1.schemas.advanced_settings import AdvancedSettingsFrontend
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


@router.get("/lidarr", response_model=LidarrSettings)
async def get_lidarr_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_lidarr_settings()
    except Exception as e:
        logger.error(f"Failed to get Lidarr settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Lidarr settings: {e}")


@router.put("/lidarr", response_model=LidarrSettings)
async def update_lidarr_settings(lidarr_settings: LidarrSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_lidarr_settings(lidarr_settings)
        logger.info(f"Updated Lidarr settings: sync_frequency={lidarr_settings.sync_frequency}")
        return lidarr_settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Lidarr settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save Lidarr settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save Lidarr settings: {e}")


@router.get("/advanced", response_model=AdvancedSettingsFrontend)
async def get_advanced_settings():
    try:
        preferences_service = get_preferences_service()
        backend_settings = preferences_service.get_advanced_settings()
        return AdvancedSettingsFrontend.from_backend(backend_settings)
    except Exception as e:
        logger.error(f"Failed to get advanced settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get advanced settings: {e}")


@router.put("/advanced", response_model=AdvancedSettingsFrontend)
async def update_advanced_settings(settings: AdvancedSettingsFrontend):
    try:
        preferences_service = get_preferences_service()
        backend_settings = settings.to_backend()
        preferences_service.save_advanced_settings(backend_settings)
        logger.info("Updated advanced settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating advanced settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.warning(f"Validation error updating advanced settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save advanced settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save advanced settings: {e}")

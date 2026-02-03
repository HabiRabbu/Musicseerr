import logging
from fastapi import APIRouter, HTTPException
from api.v1.schemas.settings import (
    UserPreferences, 
    LidarrSettings, 
    LidarrConnectionSettings,
    SoularrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    HomeSettings,
    LidarrVerifyResponse
)
from api.v1.schemas.advanced_settings import AdvancedSettingsFrontend
from core.dependencies import get_preferences_service, get_settings_service
from core.exceptions import ConfigurationError
from repositories.jellyfin_repository import JellyfinRepository
from repositories.listenbrainz_repository import ListenBrainzRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_preferences()
    except Exception as e:
        logger.exception(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(preferences: UserPreferences):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_preferences(preferences)

        settings_service = get_settings_service()
        total_cleared = await settings_service.clear_caches_for_preference_change()
        logger.info(f"Updated user preferences. Cleared {total_cleared} cache entries.")

        return preferences
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating preferences: {e}")
        raise HTTPException(status_code=400, detail="Invalid configuration")
    except Exception as e:
        logger.exception(f"Failed to save preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to save preferences")


@router.get("/lidarr", response_model=LidarrSettings)
async def get_lidarr_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_lidarr_settings()
    except Exception as e:
        logger.exception(f"Failed to get Lidarr settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Lidarr settings")


@router.put("/lidarr", response_model=LidarrSettings)
async def update_lidarr_settings(lidarr_settings: LidarrSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_lidarr_settings(lidarr_settings)
        logger.info(f"Updated Lidarr settings: sync_frequency={lidarr_settings.sync_frequency}")
        return lidarr_settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Lidarr settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid Lidarr configuration")
    except Exception as e:
        logger.exception(f"Failed to save Lidarr settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save Lidarr settings")


@router.get("/advanced", response_model=AdvancedSettingsFrontend)
async def get_advanced_settings():
    try:
        preferences_service = get_preferences_service()
        backend_settings = preferences_service.get_advanced_settings()
        return AdvancedSettingsFrontend.from_backend(backend_settings)
    except Exception as e:
        logger.exception(f"Failed to get advanced settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve advanced settings")


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
        raise HTTPException(status_code=400, detail="Invalid configuration")
    except ValueError as e:
        logger.warning(f"Validation error updating advanced settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid settings value")
    except Exception as e:
        logger.exception(f"Failed to save advanced settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save advanced settings")


@router.get("/lidarr/connection", response_model=LidarrConnectionSettings)
async def get_lidarr_connection():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_lidarr_connection()
    except Exception as e:
        logger.exception(f"Failed to get Lidarr connection settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Lidarr connection settings")


@router.put("/lidarr/connection", response_model=LidarrConnectionSettings)
async def update_lidarr_connection(settings: LidarrConnectionSettings):
    try:
        from repositories.lidarr.base import reset_lidarr_circuit_breaker
        
        preferences_service = get_preferences_service()
        preferences_service.save_lidarr_connection(settings)
        reset_lidarr_circuit_breaker()
        settings_service = get_settings_service()
        await settings_service.clear_home_cache()
        logger.info("Updated Lidarr connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Lidarr connection: {e}")
        raise HTTPException(status_code=400, detail="Invalid Lidarr connection configuration")
    except Exception as e:
        logger.exception(f"Failed to save Lidarr connection settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save Lidarr connection settings")


@router.post("/lidarr/verify", response_model=LidarrVerifyResponse)
async def verify_lidarr_connection(settings: LidarrConnectionSettings):
    settings_service = get_settings_service()
    return await settings_service.verify_lidarr(settings)


@router.get("/soularr", response_model=SoularrConnectionSettings)
async def get_soularr_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_soularr_connection()
    except Exception as e:
        logger.exception(f"Failed to get Soularr settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Soularr settings")


@router.put("/soularr", response_model=SoularrConnectionSettings)
async def update_soularr_settings(settings: SoularrConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_soularr_connection(settings)
        logger.info("Updated Soularr connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Soularr settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid Soularr configuration")
    except Exception as e:
        logger.exception(f"Failed to save Soularr settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save Soularr settings")


@router.get("/jellyfin", response_model=JellyfinConnectionSettings)
async def get_jellyfin_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_jellyfin_connection()
    except Exception as e:
        logger.exception(f"Failed to get Jellyfin settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Jellyfin settings")


@router.put("/jellyfin", response_model=JellyfinConnectionSettings)
async def update_jellyfin_settings(settings: JellyfinConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_jellyfin_connection(settings)
        JellyfinRepository.reset_circuit_breaker()
        settings_service = get_settings_service()
        await settings_service.clear_home_cache()
        logger.info("Updated Jellyfin connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Jellyfin settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid Jellyfin configuration")
    except Exception as e:
        logger.exception(f"Failed to save Jellyfin settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save Jellyfin settings")


@router.post("/jellyfin/verify")
async def verify_jellyfin_connection(settings: JellyfinConnectionSettings):
    settings_service = get_settings_service()
    result = await settings_service.verify_jellyfin(settings)
    return {
        "success": result.success,
        "message": result.message,
        "users": result.users if result.success else []
    }


@router.get("/listenbrainz", response_model=ListenBrainzConnectionSettings)
async def get_listenbrainz_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_listenbrainz_connection()
    except Exception as e:
        logger.exception(f"Failed to get ListenBrainz settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ListenBrainz settings")


@router.put("/listenbrainz", response_model=ListenBrainzConnectionSettings)
async def update_listenbrainz_settings(settings: ListenBrainzConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_listenbrainz_connection(settings)
        ListenBrainzRepository.reset_circuit_breaker()
        settings_service = get_settings_service()
        await settings_service.clear_home_cache()
        logger.info("Updated ListenBrainz connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating ListenBrainz settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid ListenBrainz configuration")
    except Exception as e:
        logger.exception(f"Failed to save ListenBrainz settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save ListenBrainz settings")


@router.post("/listenbrainz/verify")
async def verify_listenbrainz_connection(settings: ListenBrainzConnectionSettings):
    settings_service = get_settings_service()
    result = await settings_service.verify_listenbrainz(settings)
    return {"valid": result.valid, "message": result.message}


@router.get("/home", response_model=HomeSettings)
async def get_home_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_home_settings()
    except Exception as e:
        logger.exception(f"Failed to get home settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve home settings")


@router.put("/home", response_model=HomeSettings)
async def update_home_settings(settings: HomeSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_home_settings(settings)
        logger.info("Updated home settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating home settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid home configuration")
    except Exception as e:
        logger.exception(f"Failed to save home settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save home settings")

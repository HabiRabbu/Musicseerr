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
from core.dependencies import get_preferences_service, get_cache, get_lidarr_repository
from core.exceptions import ConfigurationError, ExternalServiceError

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


@router.get("/lidarr/connection", response_model=LidarrConnectionSettings)
async def get_lidarr_connection():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_lidarr_connection()
    except Exception as e:
        logger.error(f"Failed to get Lidarr connection settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Lidarr connection settings: {e}")


@router.put("/lidarr/connection", response_model=LidarrConnectionSettings)
async def update_lidarr_connection(settings: LidarrConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_lidarr_connection(settings)
        logger.info("Updated Lidarr connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Lidarr connection: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save Lidarr connection settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save Lidarr connection settings: {e}")


@router.post("/lidarr/verify", response_model=LidarrVerifyResponse)
async def verify_lidarr_connection(settings: LidarrConnectionSettings):
    try:
        lidarr_repo = get_lidarr_repository()
        
        from core.config import get_settings
        app_settings = get_settings()
        app_settings.lidarr_url = settings.lidarr_url
        app_settings.lidarr_api_key = settings.lidarr_api_key
        
        status = await lidarr_repo.get_status()
        
        if status.status != "ok":
            return LidarrVerifyResponse(
                success=False,
                message=status.message or "Connection failed",
                quality_profiles=[],
                metadata_profiles=[],
                root_folders=[]
            )
        
        quality_profiles_raw = await lidarr_repo.get_quality_profiles()
        quality_profiles = [
            {"id": int(p.get("id", 0)), "name": str(p.get("name", "Unknown"))}
            for p in quality_profiles_raw
        ]
        
        metadata_profiles_raw = await lidarr_repo.get_metadata_profiles()
        metadata_profiles = [
            {"id": int(p.get("id", 0)), "name": str(p.get("name", "Unknown"))}
            for p in metadata_profiles_raw
        ]
        
        root_folders_raw = await lidarr_repo.get_root_folders()
        root_folders = [
            {"id": str(r.get("id", "")), "path": str(r.get("path", ""))}
            for r in root_folders_raw
        ]
        
        return LidarrVerifyResponse(
            success=True,
            message="Successfully connected to Lidarr",
            quality_profiles=quality_profiles,
            metadata_profiles=metadata_profiles,
            root_folders=root_folders
        )
    except ExternalServiceError as e:
        logger.warning(f"Lidarr connection test failed: {e}")
        return LidarrVerifyResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
            quality_profiles=[],
            metadata_profiles=[],
            root_folders=[]
        )
    except Exception as e:
        logger.error(f"Failed to verify Lidarr connection: {e}")
        return LidarrVerifyResponse(
            success=False,
            message=f"Verification error: {str(e)}",
            quality_profiles=[],
            metadata_profiles=[],
            root_folders=[]
        )


@router.get("/soularr", response_model=SoularrConnectionSettings)
async def get_soularr_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_soularr_connection()
    except Exception as e:
        logger.error(f"Failed to get Soularr settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Soularr settings: {e}")


@router.put("/soularr", response_model=SoularrConnectionSettings)
async def update_soularr_settings(settings: SoularrConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_soularr_connection(settings)
        logger.info("Updated Soularr connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Soularr settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save Soularr settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save Soularr settings: {e}")


@router.get("/jellyfin", response_model=JellyfinConnectionSettings)
async def get_jellyfin_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_jellyfin_connection()
    except Exception as e:
        logger.error(f"Failed to get Jellyfin settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Jellyfin settings: {e}")


@router.put("/jellyfin", response_model=JellyfinConnectionSettings)
async def update_jellyfin_settings(settings: JellyfinConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_jellyfin_connection(settings)
        logger.info("Updated Jellyfin connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating Jellyfin settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save Jellyfin settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save Jellyfin settings: {e}")


@router.post("/jellyfin/verify")
async def verify_jellyfin_connection(settings: JellyfinConnectionSettings):
    try:
        from core.dependencies import get_jellyfin_repository
        jellyfin_repo = get_jellyfin_repository()
        
        jellyfin_repo.configure(
            base_url=settings.jellyfin_url,
            api_key=settings.api_key,
            user_id=settings.user_id
        )
        
        success, message = await jellyfin_repo.validate_connection()
        return {"success": success, "message": message}
    except Exception as e:
        logger.error(f"Failed to verify Jellyfin connection: {e}")
        return {"success": False, "message": f"Verification error: {str(e)}"}


@router.get("/listenbrainz", response_model=ListenBrainzConnectionSettings)
async def get_listenbrainz_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_listenbrainz_connection()
    except Exception as e:
        logger.error(f"Failed to get ListenBrainz settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get ListenBrainz settings: {e}")


@router.put("/listenbrainz", response_model=ListenBrainzConnectionSettings)
async def update_listenbrainz_settings(settings: ListenBrainzConnectionSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_listenbrainz_connection(settings)
        logger.info("Updated ListenBrainz connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating ListenBrainz settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save ListenBrainz settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save ListenBrainz settings: {e}")


@router.post("/listenbrainz/verify")
async def verify_listenbrainz_connection(settings: ListenBrainzConnectionSettings):
    try:
        from core.dependencies import get_listenbrainz_repository
        lb_repo = get_listenbrainz_repository()
        
        lb_repo.configure(
            username=settings.username,
            user_token=settings.user_token
        )
        
        if settings.user_token:
            valid, message = await lb_repo.validate_token()
        else:
            valid, message = await lb_repo.validate_username(settings.username)
        
        return {"valid": valid, "message": message}
    except Exception as e:
        logger.error(f"Failed to verify ListenBrainz connection: {e}")
        return {"valid": False, "message": f"Verification error: {str(e)}"}


@router.get("/home", response_model=HomeSettings)
async def get_home_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_home_settings()
    except Exception as e:
        logger.error(f"Failed to get home settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get home settings: {e}")


@router.put("/home", response_model=HomeSettings)
async def update_home_settings(settings: HomeSettings):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_home_settings(settings)
        logger.info("Updated home settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating home settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save home settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save home settings: {e}")

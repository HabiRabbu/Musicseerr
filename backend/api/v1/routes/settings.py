import logging
from fastapi import APIRouter, Depends, HTTPException
from api.v1.schemas.settings import (
    UserPreferences, 
    LidarrSettings, 
    LidarrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    YouTubeConnectionSettings,
    HomeSettings,
    LidarrVerifyResponse,
    LocalFilesConnectionSettings,
    LocalFilesVerifyResponse,
)
from api.v1.schemas.advanced_settings import AdvancedSettingsFrontend, FrontendCacheTTLs
from core.dependencies import (
    get_preferences_service,
    get_settings_service,
    get_youtube_repo,
    get_local_files_service,
    get_jellyfin_repository,
    get_stream_service,
    get_jellyfin_playback_service,
    get_jellyfin_library_service,
    get_home_service,
    get_home_charts_service,
    get_library_cache,
)
from core.exceptions import ConfigurationError
from repositories.jellyfin_repository import JellyfinRepository
from repositories.listenbrainz_repository import ListenBrainzRepository
from repositories.youtube import YouTubeRepository
from services.local_files_service import LocalFilesService
from services.preferences_service import PreferencesService
from services.settings_service import SettingsService

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


@router.get("/cache-ttls", response_model=FrontendCacheTTLs)
async def get_frontend_cache_ttls():
    try:
        preferences_service = get_preferences_service()
        backend_settings = preferences_service.get_advanced_settings()
        return FrontendCacheTTLs(
            home=backend_settings.frontend_ttl_home,
            discover=backend_settings.frontend_ttl_discover,
            library=backend_settings.frontend_ttl_library,
            recently_added=backend_settings.frontend_ttl_recently_added,
            discover_queue=backend_settings.frontend_ttl_discover_queue,
            search=backend_settings.frontend_ttl_search,
            local_files_sidebar=backend_settings.frontend_ttl_local_files_sidebar,
            jellyfin_sidebar=backend_settings.frontend_ttl_jellyfin_sidebar,
        )
    except Exception as e:
        logger.exception(f"Failed to get frontend cache TTLs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache TTLs")


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

        get_jellyfin_repository.cache_clear()
        get_stream_service.cache_clear()
        get_jellyfin_playback_service.cache_clear()
        get_jellyfin_library_service.cache_clear()
        get_home_service.cache_clear()
        get_home_charts_service.cache_clear()

        library_cache = get_library_cache()
        await library_cache.clear_jellyfin_mbid_index()

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


@router.get("/youtube", response_model=YouTubeConnectionSettings)
async def get_youtube_settings(
    preferences_service: PreferencesService = Depends(get_preferences_service),
):
    try:
        return preferences_service.get_youtube_connection()
    except Exception as e:
        logger.exception(f"Failed to get YouTube settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve YouTube settings")


@router.put("/youtube", response_model=YouTubeConnectionSettings)
async def update_youtube_settings(
    settings: YouTubeConnectionSettings,
    preferences_service: PreferencesService = Depends(get_preferences_service),
):
    try:
        preferences_service.save_youtube_connection(settings)
        get_youtube_repo.cache_clear()
        logger.info("Updated YouTube connection settings")
        return settings
    except ConfigurationError as e:
        logger.warning(f"Configuration error updating YouTube settings: {e}")
        raise HTTPException(status_code=400, detail="Invalid YouTube configuration")
    except Exception as e:
        logger.exception(f"Failed to save YouTube settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save YouTube settings")


@router.post("/youtube/verify")
async def verify_youtube_connection(settings: YouTubeConnectionSettings):
    from infrastructure.http.client import get_http_client
    from core.config import get_settings as get_app_settings

    app_settings = get_app_settings()
    http_client = get_http_client(app_settings)
    temp_repo = YouTubeRepository(
        http_client=http_client,
        api_key=settings.api_key,
        daily_quota_limit=settings.daily_quota_limit,
    )
    valid, message = await temp_repo.verify_api_key(settings.api_key)
    return {"valid": valid, "message": message}


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


@router.get("/local-files", response_model=LocalFilesConnectionSettings)
async def get_local_files_settings(
    preferences_service: PreferencesService = Depends(get_preferences_service),
):
    try:
        return preferences_service.get_local_files_connection()
    except Exception as e:
        logger.exception("Failed to get local files settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve local files settings")


@router.put("/local-files", response_model=LocalFilesConnectionSettings)
async def update_local_files_settings(
    settings: LocalFilesConnectionSettings,
    preferences_service: PreferencesService = Depends(get_preferences_service),
    settings_service: SettingsService = Depends(get_settings_service),
):
    try:
        preferences_service.save_local_files_connection(settings)
        await settings_service.clear_local_files_cache()
        logger.info("Updated local files settings")
        return settings
    except ConfigurationError as e:
        logger.warning("Configuration error updating local files settings: %s", e)
        raise HTTPException(status_code=400, detail="Invalid local files configuration")
    except Exception as e:
        logger.exception("Failed to save local files settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save local files settings")


@router.post("/local-files/verify", response_model=LocalFilesVerifyResponse)
async def verify_local_files_connection(
    settings: LocalFilesConnectionSettings,
    local_service: LocalFilesService = Depends(get_local_files_service),
) -> LocalFilesVerifyResponse:
    return await local_service.verify_path(settings.music_path)

import logging
from fastapi import APIRouter, Depends, HTTPException
from api.v1.schemas.settings import (
    UserPreferences, 
    LidarrSettings, 
    LidarrConnectionSettings,
    JellyfinConnectionSettings,
    JellyfinVerifyResponse,
    JellyfinUserInfo,
    ListenBrainzConnectionSettings,
    YouTubeConnectionSettings,
    HomeSettings,
    LidarrVerifyResponse,
    LocalFilesConnectionSettings,
    LocalFilesVerifyResponse,
    LidarrMetadataProfilePreferences,
    LidarrMetadataProfileSummary,
    LastFmConnectionSettings,
    LastFmConnectionSettingsResponse,
    LastFmVerifyResponse,
    ScrobbleSettings,
    PrimaryMusicSourceSettings,
    LASTFM_SECRET_MASK,
)
from api.v1.schemas.common import VerifyConnectionResponse
from api.v1.schemas.advanced_settings import AdvancedSettingsFrontend, FrontendCacheTTLs
from core.dependencies import (
    get_preferences_service,
    get_settings_service,
    get_coverart_repository,
    get_youtube_repo,
    get_local_files_service,
    get_jellyfin_repository,
    get_stream_service,
    get_jellyfin_playback_service,
    get_jellyfin_library_service,
    get_home_service,
    get_home_charts_service,
    get_library_cache,
    get_lastfm_repository,
    get_lastfm_auth_service,
    clear_lastfm_dependent_caches,
)
from core.exceptions import ConfigurationError, ExternalServiceError
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from repositories.jellyfin_repository import JellyfinRepository
from repositories.listenbrainz_repository import ListenBrainzRepository
from repositories.youtube import YouTubeRepository
from repositories.lastfm_repository import LastFmRepository
from services.local_files_service import LocalFilesService
from services.preferences_service import PreferencesService
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/api/settings", tags=["settings"])


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_preferences()
    except Exception as e:
        logger.exception(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(preferences: UserPreferences = MsgSpecBody(UserPreferences)):
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
async def update_lidarr_settings(lidarr_settings: LidarrSettings = MsgSpecBody(LidarrSettings)):
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
            discover_queue_polling_interval=backend_settings.discover_queue_polling_interval,
            discover_queue_auto_generate=backend_settings.discover_queue_auto_generate,
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
async def update_advanced_settings(
    settings: AdvancedSettingsFrontend = MsgSpecBody(AdvancedSettingsFrontend),
):
    try:
        preferences_service = get_preferences_service()
        backend_settings = settings.to_backend()
        preferences_service.save_advanced_settings(backend_settings)
        get_coverart_repository.cache_clear()
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
async def update_lidarr_connection(
    settings: LidarrConnectionSettings = MsgSpecBody(LidarrConnectionSettings),
):
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
async def verify_lidarr_connection(
    settings: LidarrConnectionSettings = MsgSpecBody(LidarrConnectionSettings),
):
    settings_service = get_settings_service()
    return await settings_service.verify_lidarr(settings)


@router.get(
    "/lidarr/metadata-profiles",
    response_model=list[LidarrMetadataProfileSummary],
)
async def list_lidarr_metadata_profiles():
    try:
        settings_service = get_settings_service()
        return await settings_service.list_lidarr_metadata_profiles()
    except ExternalServiceError as e:
        logger.warning(f"Lidarr metadata profiles list failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to list Lidarr metadata profiles: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list metadata profiles from Lidarr",
        )


@router.get(
    "/lidarr/metadata-profile/preferences",
    response_model=LidarrMetadataProfilePreferences,
)
async def get_lidarr_metadata_profile_preferences(
    profile_id: int | None = None,
):
    try:
        settings_service = get_settings_service()
        return await settings_service.get_lidarr_metadata_profile_preferences(
            profile_id=profile_id
        )
    except ExternalServiceError as e:
        logger.warning(f"Lidarr metadata profile fetch failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to get Lidarr metadata profile preferences: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch metadata profile from Lidarr",
        )


@router.put(
    "/lidarr/metadata-profile/preferences",
    response_model=LidarrMetadataProfilePreferences,
)
async def update_lidarr_metadata_profile_preferences(
    preferences: UserPreferences = MsgSpecBody(UserPreferences),
    profile_id: int | None = None,
):
    try:
        settings_service = get_settings_service()
        return await settings_service.update_lidarr_metadata_profile(
            preferences, profile_id=profile_id
        )
    except ExternalServiceError as e:
        logger.warning(f"Lidarr metadata profile update failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to update Lidarr metadata profile: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update metadata profile in Lidarr",
        )


@router.get("/jellyfin", response_model=JellyfinConnectionSettings)
async def get_jellyfin_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_jellyfin_connection()
    except Exception as e:
        logger.exception(f"Failed to get Jellyfin settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Jellyfin settings")


@router.put("/jellyfin", response_model=JellyfinConnectionSettings)
async def update_jellyfin_settings(
    settings: JellyfinConnectionSettings = MsgSpecBody(JellyfinConnectionSettings),
):
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


@router.post("/jellyfin/verify", response_model=JellyfinVerifyResponse)
async def verify_jellyfin_connection(
    settings: JellyfinConnectionSettings = MsgSpecBody(JellyfinConnectionSettings),
):
    settings_service = get_settings_service()
    result = await settings_service.verify_jellyfin(settings)
    users = [JellyfinUserInfo(id=user.id, name=user.name) for user in (result.users or [])] if result.success else []
    return JellyfinVerifyResponse(success=result.success, message=result.message, users=users)


@router.get("/listenbrainz", response_model=ListenBrainzConnectionSettings)
async def get_listenbrainz_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_listenbrainz_connection()
    except Exception as e:
        logger.exception(f"Failed to get ListenBrainz settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ListenBrainz settings")


@router.put("/listenbrainz", response_model=ListenBrainzConnectionSettings)
async def update_listenbrainz_settings(
    settings: ListenBrainzConnectionSettings = MsgSpecBody(ListenBrainzConnectionSettings),
):
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


@router.post("/listenbrainz/verify", response_model=VerifyConnectionResponse)
async def verify_listenbrainz_connection(
    settings: ListenBrainzConnectionSettings = MsgSpecBody(ListenBrainzConnectionSettings),
):
    settings_service = get_settings_service()
    result = await settings_service.verify_listenbrainz(settings)
    return VerifyConnectionResponse(valid=result.valid, message=result.message)


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
    settings: YouTubeConnectionSettings = MsgSpecBody(YouTubeConnectionSettings),
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


@router.post("/youtube/verify", response_model=VerifyConnectionResponse)
async def verify_youtube_connection(
    settings: YouTubeConnectionSettings = MsgSpecBody(YouTubeConnectionSettings),
):
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
    return VerifyConnectionResponse(valid=valid, message=message)


@router.get("/home", response_model=HomeSettings)
async def get_home_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_home_settings()
    except Exception as e:
        logger.exception(f"Failed to get home settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve home settings")


@router.put("/home", response_model=HomeSettings)
async def update_home_settings(settings: HomeSettings = MsgSpecBody(HomeSettings)):
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
    settings: LocalFilesConnectionSettings = MsgSpecBody(LocalFilesConnectionSettings),
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
    settings: LocalFilesConnectionSettings = MsgSpecBody(LocalFilesConnectionSettings),
    local_service: LocalFilesService = Depends(get_local_files_service),
) -> LocalFilesVerifyResponse:
    return await local_service.verify_path(settings.music_path)


@router.get("/lastfm", response_model=LastFmConnectionSettingsResponse)
async def get_lastfm_settings():
    try:
        preferences_service = get_preferences_service()
        settings = preferences_service.get_lastfm_connection()
        return LastFmConnectionSettingsResponse.from_settings(settings)
    except Exception as e:
        logger.exception("Failed to get Last.fm settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve Last.fm settings")


@router.put("/lastfm", response_model=LastFmConnectionSettingsResponse)
async def update_lastfm_settings(
    settings: LastFmConnectionSettings = MsgSpecBody(LastFmConnectionSettings),
):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_lastfm_connection(settings)
        LastFmRepository.reset_circuit_breaker()
        get_lastfm_repository.cache_clear()
        get_lastfm_auth_service.cache_clear()
        clear_lastfm_dependent_caches()
        settings_service = get_settings_service()
        await settings_service.clear_home_cache()
        logger.info("Updated Last.fm connection settings")
        saved = preferences_service.get_lastfm_connection()
        return LastFmConnectionSettingsResponse.from_settings(saved)
    except ConfigurationError as e:
        logger.warning("Configuration error updating Last.fm settings: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Last.fm configuration")
    except Exception as e:
        logger.exception("Failed to save Last.fm settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save Last.fm settings")


@router.post("/lastfm/verify", response_model=LastFmVerifyResponse)
async def verify_lastfm_connection(
    settings: LastFmConnectionSettings = MsgSpecBody(LastFmConnectionSettings),
):
    from infrastructure.http.client import get_http_client
    from core.config import get_settings as get_app_settings
    from infrastructure.cache.memory_cache import InMemoryCache

    try:
        app_settings = get_app_settings()
        http_client = get_http_client(app_settings)

        preferences_service = get_preferences_service()
        current = preferences_service.get_lastfm_connection()
        shared_secret = settings.shared_secret
        if shared_secret.startswith(LASTFM_SECRET_MASK):
            shared_secret = current.shared_secret

        session_key = settings.session_key
        if session_key.startswith(LASTFM_SECRET_MASK):
            session_key = current.session_key

        temp_repo = LastFmRepository(
            http_client=http_client,
            cache=InMemoryCache(),
            api_key=settings.api_key,
            shared_secret=shared_secret,
            session_key=session_key,
        )
        valid, message = await temp_repo.validate_api_key()
        if not valid:
            return LastFmVerifyResponse(valid=False, message=message)

        if session_key:
            session_valid, session_message = await temp_repo.validate_session()
            if not session_valid:
                return LastFmVerifyResponse(
                    valid=False,
                    message=f"API key valid, but session invalid: {session_message}",
                )
            return LastFmVerifyResponse(valid=True, message=session_message)

        return LastFmVerifyResponse(valid=valid, message=message)
    except Exception as e:
        logger.exception("Failed to verify Last.fm connection: %s", e)
        return LastFmVerifyResponse(valid=False, message="Verification error")


@router.get("/scrobble", response_model=ScrobbleSettings)
async def get_scrobble_settings():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_scrobble_settings()
    except Exception as e:
        logger.exception("Failed to get scrobble settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve scrobble settings")


@router.put("/scrobble", response_model=ScrobbleSettings)
async def update_scrobble_settings(
    settings: ScrobbleSettings = MsgSpecBody(ScrobbleSettings),
):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_scrobble_settings(settings)
        logger.info("Updated scrobble settings")
        return preferences_service.get_scrobble_settings()
    except ConfigurationError as e:
        logger.warning("Configuration error updating scrobble settings: %s", e)
        raise HTTPException(status_code=400, detail="Invalid scrobble configuration")
    except Exception as e:
        logger.exception("Failed to save scrobble settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save scrobble settings")


@router.get("/primary-source", response_model=PrimaryMusicSourceSettings)
async def get_primary_music_source():
    try:
        preferences_service = get_preferences_service()
        return preferences_service.get_primary_music_source()
    except Exception as e:
        logger.exception("Failed to get primary music source: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve primary music source")


@router.put("/primary-source", response_model=PrimaryMusicSourceSettings)
async def update_primary_music_source(
    settings: PrimaryMusicSourceSettings = MsgSpecBody(PrimaryMusicSourceSettings),
):
    try:
        preferences_service = get_preferences_service()
        preferences_service.save_primary_music_source(settings)
        settings_service = get_settings_service()
        await settings_service.clear_home_cache()
        logger.info("Updated primary music source to %s", settings.source)
        return preferences_service.get_primary_music_source()
    except ConfigurationError as e:
        logger.warning("Configuration error updating primary music source: %s", e)
        raise HTTPException(status_code=400, detail="Invalid primary music source")
    except Exception as e:
        logger.exception("Failed to save primary music source: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save primary music source")

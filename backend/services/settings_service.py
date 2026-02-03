import logging
from dataclasses import dataclass

from api.v1.schemas.settings import (
    LidarrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    LidarrVerifyResponse,
)
from core.config import Settings, get_settings
from core.exceptions import ExternalServiceError
from infrastructure.cache.memory_cache import InMemoryCache, CacheInterface
from infrastructure.http.client import get_http_client

logger = logging.getLogger(__name__)


@dataclass
class JellyfinUser:
    id: str
    name: str


@dataclass
class JellyfinVerifyResult:
    success: bool
    message: str
    users: list[JellyfinUser] | None = None


@dataclass
class ListenBrainzVerifyResult:
    valid: bool
    message: str


class SettingsService:
    def __init__(self, preferences_service, cache: CacheInterface):
        self._preferences_service = preferences_service
        self._cache = cache

    async def verify_lidarr(self, settings: LidarrConnectionSettings) -> LidarrVerifyResponse:
        try:
            from repositories.lidarr import LidarrRepository
            from repositories.lidarr.base import reset_lidarr_circuit_breaker
            
            reset_lidarr_circuit_breaker()

            app_settings = get_settings()
            http_client = get_http_client(app_settings)

            temp_settings = Settings(
                lidarr_url=settings.lidarr_url,
                lidarr_api_key=settings.lidarr_api_key,
                quality_profile_id=app_settings.quality_profile_id,
                metadata_profile_id=app_settings.metadata_profile_id,
            )
            temp_cache = InMemoryCache(max_entries=100)

            temp_repo = LidarrRepository(
                settings=temp_settings,
                http_client=http_client,
                cache=temp_cache
            )

            status = await temp_repo.get_status()

            if status.status != "ok":
                return LidarrVerifyResponse(
                    success=False,
                    message=status.message or "Connection failed",
                    quality_profiles=[],
                    metadata_profiles=[],
                    root_folders=[]
                )

            quality_profiles_raw = await temp_repo.get_quality_profiles()
            quality_profiles = [
                {"id": int(p.get("id", 0)), "name": str(p.get("name", "Unknown"))}
                for p in quality_profiles_raw
            ]

            metadata_profiles_raw = await temp_repo.get_metadata_profiles()
            metadata_profiles = [
                {"id": int(p.get("id", 0)), "name": str(p.get("name", "Unknown"))}
                for p in metadata_profiles_raw
            ]

            root_folders_raw = await temp_repo.get_root_folders()
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
                message="Connection failed: Unable to reach Lidarr",
                quality_profiles=[],
                metadata_profiles=[],
                root_folders=[]
            )
        except Exception as e:
            logger.exception(f"Failed to verify Lidarr connection: {e}")
            return LidarrVerifyResponse(
                success=False,
                message="Verification error: Unable to complete connection test",
                quality_profiles=[],
                metadata_profiles=[],
                root_folders=[]
            )

    async def verify_jellyfin(self, settings: JellyfinConnectionSettings) -> JellyfinVerifyResult:
        try:
            from repositories.jellyfin_repository import JellyfinRepository
            
            JellyfinRepository.reset_circuit_breaker()

            app_settings = get_settings()
            http_client = get_http_client(app_settings)
            temp_cache = InMemoryCache(max_entries=100)

            temp_repo = JellyfinRepository(http_client=http_client, cache=temp_cache)
            temp_repo.configure(
                base_url=settings.jellyfin_url,
                api_key=settings.api_key,
                user_id=settings.user_id
            )

            success, message = await temp_repo.validate_connection()
            
            users = []
            if success:
                jf_users = await temp_repo.fetch_users_direct()
                users = [JellyfinUser(id=u.id, name=u.name) for u in jf_users]
            
            return JellyfinVerifyResult(success=success, message=message, users=users)
        except Exception as e:
            logger.exception(f"Failed to verify Jellyfin connection: {e}")
            return JellyfinVerifyResult(
                success=False,
                message="Verification error: Unable to complete connection test"
            )

    async def verify_listenbrainz(self, settings: ListenBrainzConnectionSettings) -> ListenBrainzVerifyResult:
        try:
            from repositories.listenbrainz_repository import ListenBrainzRepository
            
            ListenBrainzRepository.reset_circuit_breaker()

            app_settings = get_settings()
            http_client = get_http_client(app_settings)
            temp_cache = InMemoryCache(max_entries=100)

            temp_repo = ListenBrainzRepository(http_client=http_client, cache=temp_cache)
            temp_repo.configure(
                username=settings.username,
                user_token=settings.user_token
            )

            if settings.user_token:
                valid, message = await temp_repo.validate_token()
            else:
                valid, message = await temp_repo.validate_username(settings.username)

            return ListenBrainzVerifyResult(valid=valid, message=message)
        except Exception as e:
            logger.exception(f"Failed to verify ListenBrainz connection: {e}")
            return ListenBrainzVerifyResult(
                valid=False,
                message="Verification error: Unable to complete connection test"
            )

    async def clear_caches_for_preference_change(self) -> int:
        cleared_artist = await self._cache.clear_prefix("artist:")
        cleared_mb_artist = await self._cache.clear_prefix("mb_artist_detail:")
        cleared_mb_artists = await self._cache.clear_prefix("mb_artists:")
        cleared_mb_albums = await self._cache.clear_prefix("mb_albums:")
        total_cleared = cleared_artist + cleared_mb_artist + cleared_mb_artists + cleared_mb_albums
        logger.info(f"Cleared {total_cleared} cache entries for preference change")
        return total_cleared
    
    async def clear_home_cache(self) -> int:
        cleared_home = await self._cache.clear_prefix("home_response:")
        cleared_jf = await self._cache.clear_prefix("jellyfin_")
        cleared_lb = await self._cache.clear_prefix("listenbrainz_")
        total = cleared_home + cleared_jf + cleared_lb
        logger.info(f"Cleared {total} home/integration cache entries")
        return total

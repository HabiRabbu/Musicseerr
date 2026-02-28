import logging

import msgspec

from api.v1.schemas.settings import (
    LidarrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    LidarrVerifyResponse,
    LidarrMetadataProfilePreferences,
    UserPreferences,
    LidarrProfileSummary,
    LidarrRootFolderSummary,
)
from core.config import Settings, get_settings
from core.exceptions import ExternalServiceError
from infrastructure.cache.memory_cache import InMemoryCache, CacheInterface
from infrastructure.http.client import get_http_client
from repositories.jellyfin_models import JellyfinUser

logger = logging.getLogger(__name__)


class JellyfinVerifyResult(msgspec.Struct):
    success: bool
    message: str
    users: list[JellyfinUser] | None = None


class ListenBrainzVerifyResult(msgspec.Struct):
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
                 LidarrProfileSummary(id=int(p.get("id", 0)), name=str(p.get("name", "Unknown")))
                for p in quality_profiles_raw
            ]

            metadata_profiles_raw = await temp_repo.get_metadata_profiles()
            metadata_profiles = [
                 LidarrProfileSummary(id=int(p.get("id", 0)), name=str(p.get("name", "Unknown")))
                for p in metadata_profiles_raw
            ]

            root_folders_raw = await temp_repo.get_root_folders()
            root_folders = [
                 LidarrRootFolderSummary(id=str(r.get("id", "")), path=str(r.get("path", "")))
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
        cleared_discover = await self._cache.clear_prefix("discover_response:")
        cleared_lfm = await self._cache.clear_prefix("lastfm_")
        total = cleared_home + cleared_jf + cleared_lb + cleared_discover + cleared_lfm
        logger.info(f"Cleared {total} home/discover/integration cache entries")
        return total

    async def clear_local_files_cache(self) -> int:
        cleared = await self._cache.clear_prefix("local_files_")
        logger.info(f"Cleared {cleared} local files cache entries")
        return cleared

    def _create_lidarr_repo(self) -> "LidarrRepository":
        from repositories.lidarr import LidarrRepository

        app_settings = get_settings()
        if not app_settings.lidarr_url or not app_settings.lidarr_api_key:
            raise ExternalServiceError("Lidarr is not configured")

        http_client = get_http_client(app_settings)
        temp_cache = InMemoryCache(max_entries=100)
        return LidarrRepository(
            settings=app_settings,
            http_client=http_client,
            cache=temp_cache,
        )

    @staticmethod
    def _lidarr_profile_to_preferences(profile: dict) -> LidarrMetadataProfilePreferences:
        primary = [
            item["albumType"]["name"].lower()
            for item in profile.get("primaryAlbumTypes", [])
            if item.get("allowed")
        ]
        secondary = [
            item["albumType"]["name"].lower()
            for item in profile.get("secondaryAlbumTypes", [])
            if item.get("allowed")
        ]
        statuses = [
            item["releaseStatus"]["name"].lower()
            for item in profile.get("releaseStatuses", [])
            if item.get("allowed")
        ]
        return LidarrMetadataProfilePreferences(
            profile_id=profile["id"],
            profile_name=profile.get("name", "Unknown"),
            primary_types=primary,
            secondary_types=secondary,
            release_statuses=statuses,
        )

    @staticmethod
    def _apply_preferences_to_profile(
        profile: dict, preferences: UserPreferences
    ) -> dict:
        for item in profile.get("primaryAlbumTypes", []):
            name = item["albumType"]["name"].lower()
            item["allowed"] = name in preferences.primary_types
        for item in profile.get("secondaryAlbumTypes", []):
            name = item["albumType"]["name"].lower()
            item["allowed"] = name in preferences.secondary_types
        for item in profile.get("releaseStatuses", []):
            name = item["releaseStatus"]["name"].lower()
            item["allowed"] = name in preferences.release_statuses
        return profile

    def _resolve_profile_id(self, profile_id: int | None) -> int:
        if profile_id is not None:
            return profile_id
        connection = self._preferences_service.get_lidarr_connection()
        return connection.metadata_profile_id

    async def list_lidarr_metadata_profiles(
        self,
    ) -> list[dict]:
        repo = self._create_lidarr_repo()
        try:
            profiles = await repo.get_metadata_profiles()
        except Exception as e:
            logger.error(f"Failed to list Lidarr metadata profiles: {e}")
            raise ExternalServiceError(
                f"Failed to list Lidarr metadata profiles: {e}"
            )
        return [{"id": p["id"], "name": p["name"]} for p in profiles]

    async def get_lidarr_metadata_profile_preferences(
        self,
        profile_id: int | None = None,
    ) -> LidarrMetadataProfilePreferences:
        resolved_id = self._resolve_profile_id(profile_id)

        repo = self._create_lidarr_repo()
        try:
            profile = await repo.get_metadata_profile(resolved_id)
        except Exception as e:
            logger.error(f"Failed to fetch Lidarr metadata profile {resolved_id}: {e}")
            raise ExternalServiceError(
                f"Failed to fetch Lidarr metadata profile: {e}"
            )

        return self._lidarr_profile_to_preferences(profile)

    async def update_lidarr_metadata_profile(
        self,
        preferences: UserPreferences,
        profile_id: int | None = None,
    ) -> LidarrMetadataProfilePreferences:
        resolved_id = self._resolve_profile_id(profile_id)

        repo = self._create_lidarr_repo()
        try:
            profile = await repo.get_metadata_profile(resolved_id)
        except Exception as e:
            logger.error(f"Failed to fetch Lidarr metadata profile {resolved_id}: {e}")
            raise ExternalServiceError(
                f"Failed to fetch Lidarr metadata profile: {e}"
            )

        updated_profile = self._apply_preferences_to_profile(profile, preferences)

        validations = [
            (
                "primaryAlbumTypes",
                "primary album type",
                "e.g. Album",
            ),
            (
                "secondaryAlbumTypes",
                "secondary album type",
                "e.g. Studio",
            ),
            (
                "releaseStatuses",
                "release status",
                "e.g. Official",
            ),
        ]
        for key, label, example in validations:
            if not any(item.get("allowed") for item in updated_profile.get(key, [])):
                raise ExternalServiceError(
                    f"Lidarr requires at least one {label} to be enabled. "
                    f"Please enable at least one ({example}) before syncing."
                )

        try:
            result = await repo.update_metadata_profile(resolved_id, updated_profile)
        except Exception as e:
            logger.error(f"Failed to update Lidarr metadata profile {resolved_id}: {e}")
            raise ExternalServiceError(
                f"Failed to update Lidarr metadata profile: {e}"
            )

        logger.info(f"Updated Lidarr metadata profile '{result.get('name')}' (ID: {resolved_id})")
        return self._lidarr_profile_to_preferences(result)

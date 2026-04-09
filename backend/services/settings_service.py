import logging

import msgspec

from api.v1.schemas.settings import (
    LidarrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    NavidromeConnectionSettings,
    YouTubeConnectionSettings,
    LastFmConnectionSettings,
    LidarrVerifyResponse,
    LidarrMetadataProfilePreferences,
    UserPreferences,
    LidarrProfileSummary,
    LidarrRootFolderSummary,
    NAVIDROME_PASSWORD_MASK,
    LASTFM_SECRET_MASK,
    PlexConnectionSettings,
    PLEX_TOKEN_MASK,
)
from core.config import Settings, get_settings
from core.exceptions import ExternalServiceError
from infrastructure.cache.cache_keys import (
    ARTIST_INFO_PREFIX,
    ALBUM_INFO_PREFIX,
    JELLYFIN_PREFIX,
    LOCAL_FILES_PREFIX,
    SOURCE_RESOLUTION_PREFIX,
    PLEX_PREFIX,
    musicbrainz_prefixes,
    listenbrainz_prefixes,
    lastfm_prefixes,
    home_prefixes,
)
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


class NavidromeVerifyResult(msgspec.Struct):
    valid: bool
    message: str


class PlexVerifyResult(msgspec.Struct):
    valid: bool
    message: str
    libraries: list[tuple[str, str]] = []


class YouTubeVerifyResult(msgspec.Struct):
    valid: bool
    message: str


class LastFmVerifyResult(msgspec.Struct):
    valid: bool
    message: str


class SettingsService:
    def __init__(self, preferences_service, cache: CacheInterface):
        self._preferences_service = preferences_service
        self._cache = cache

    async def verify_lidarr(self, settings: LidarrConnectionSettings) -> LidarrVerifyResponse:
        try:
            from infrastructure.validators import validate_service_url
            validate_service_url(settings.lidarr_url, label="Lidarr URL")

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
                    message=status.message or "Couldn't connect",
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
                message="Connected to Lidarr",
                quality_profiles=quality_profiles,
                metadata_profiles=metadata_profiles,
                root_folders=root_folders
            )
        except ExternalServiceError as e:
            detail = str(e)
            logger.warning(f"Lidarr connection test failed: {detail}")
            if "No address associated with hostname" in detail or "Name or service not known" in detail:
                hint = "DNS resolution failed. Check that the hostname is reachable from inside the container"
            elif "Connection refused" in detail:
                hint = "Connection refused. Check the port and make sure Lidarr is running"
            elif "timed out" in detail.lower() or "timeout" in detail.lower():
                hint = "Connection timed out. Check your network and firewall settings"
            else:
                hint = detail
            return LidarrVerifyResponse(
                success=False,
                message=f"Couldn't reach Lidarr: {hint}",
                quality_profiles=[],
                metadata_profiles=[],
                root_folders=[]
            )
        except Exception as e:
            logger.exception(f"Failed to verify Lidarr connection: {e}")
            return LidarrVerifyResponse(
                success=False,
                message=f"Couldn't finish the connection test: {e}",
                quality_profiles=[],
                metadata_profiles=[],
                root_folders=[]
            )

    async def verify_jellyfin(self, settings: JellyfinConnectionSettings) -> JellyfinVerifyResult:
        try:
            from infrastructure.validators import validate_service_url
            validate_service_url(settings.jellyfin_url, label="Jellyfin URL")

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
                message="Couldn't finish the connection test"
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
                message="Couldn't finish the connection test"
            )

    async def clear_caches_for_preference_change(self) -> int:
        total = 0
        total += await self._cache.clear_prefix(ARTIST_INFO_PREFIX)
        total += await self._cache.clear_prefix(ALBUM_INFO_PREFIX)
        for prefix in musicbrainz_prefixes():
            total += await self._cache.clear_prefix(prefix)
        logger.info(f"Cleared {total} cache entries for preference change")
        return total

    async def clear_home_cache(self) -> int:
        total = 0
        for prefix in home_prefixes():
            total += await self._cache.clear_prefix(prefix)
        total += await self._cache.clear_prefix(JELLYFIN_PREFIX)
        for prefix in listenbrainz_prefixes():
            total += await self._cache.clear_prefix(prefix)
        for prefix in lastfm_prefixes():
            total += await self._cache.clear_prefix(prefix)
        logger.info(f"Cleared {total} home/discover/integration cache entries")
        return total

    async def clear_local_files_cache(self) -> int:
        cleared = await self._cache.clear_prefix(LOCAL_FILES_PREFIX)
        logger.info(f"Cleared {cleared} local files cache entries")
        return cleared

    async def clear_source_resolution_cache(self) -> int:
        cleared = await self._cache.clear_prefix(SOURCE_RESOLUTION_PREFIX)
        logger.info(f"Cleared {cleared} source-resolution cache entries")
        return cleared

    async def on_jellyfin_settings_changed(self) -> None:
        """Full cache/state reset when Jellyfin settings change."""
        from repositories.jellyfin_repository import JellyfinRepository
        from core.dependencies import (
            get_jellyfin_repository, get_jellyfin_playback_service,
            get_jellyfin_library_service, get_home_service,
            get_home_charts_service, get_mbid_store,
        )
        JellyfinRepository.reset_circuit_breaker()
        get_jellyfin_repository.cache_clear()
        get_jellyfin_playback_service.cache_clear()
        get_jellyfin_library_service.cache_clear()
        get_home_service.cache_clear()
        get_home_charts_service.cache_clear()
        mbid_store = get_mbid_store()
        await mbid_store.clear_jellyfin_mbid_index()
        await self.clear_home_cache()
        await self.clear_source_resolution_cache()
        logger.info("Jellyfin settings change: all caches/singletons reset")

    async def on_navidrome_settings_changed(self, enabled: bool = False) -> None:
        """Full cache/state reset when Navidrome settings change."""
        from repositories.navidrome_repository import NavidromeRepository
        from core.dependencies import (
            get_navidrome_repository, get_navidrome_library_service,
            get_navidrome_playback_service, get_home_service,
            get_home_charts_service, get_mbid_store,
        )
        NavidromeRepository.reset_circuit_breaker()
        get_navidrome_repository.cache_clear()
        get_navidrome_library_service.cache_clear()
        get_navidrome_playback_service.cache_clear()
        get_home_service.cache_clear()
        get_home_charts_service.cache_clear()
        mbid_store = get_mbid_store()
        await mbid_store.clear_navidrome_mbid_indexes()
        new_repo = get_navidrome_repository()
        await new_repo.clear_cache()
        await self.clear_home_cache()
        await self.clear_source_resolution_cache()
        if enabled:
            import asyncio
            from core.tasks import warm_navidrome_mbid_cache
            from core.task_registry import TaskRegistry
            registry = TaskRegistry.get_instance()
            if not registry.is_running("navidrome-mbid-warmup"):
                _nav_task = asyncio.create_task(warm_navidrome_mbid_cache())
                try:
                    registry.register("navidrome-mbid-warmup", _nav_task)
                except RuntimeError:
                    pass
        logger.info("Navidrome settings change: all caches/singletons reset")

    async def on_lastfm_settings_changed(self) -> None:
        """Full cache/state reset when Last.fm settings change."""
        from repositories.lastfm_repository import LastFmRepository
        from core.dependencies import (
            get_lastfm_repository, get_lastfm_auth_service,
            clear_lastfm_dependent_caches,
        )
        LastFmRepository.reset_circuit_breaker()
        get_lastfm_repository.cache_clear()
        get_lastfm_auth_service.cache_clear()
        clear_lastfm_dependent_caches()
        await self.clear_home_cache()
        logger.info("Last.fm settings change: all caches/singletons reset")

    async def on_listenbrainz_settings_changed(self) -> None:
        """Full cache/state reset when ListenBrainz settings change."""
        from repositories.listenbrainz_repository import ListenBrainzRepository
        from core.dependencies import clear_listenbrainz_dependent_caches
        ListenBrainzRepository.reset_circuit_breaker()
        clear_listenbrainz_dependent_caches()
        await self.clear_home_cache()
        logger.info("ListenBrainz settings change: all caches/singletons reset")

    async def on_youtube_settings_changed(self) -> None:
        """Reset YouTube singleton and clear home caches when settings change."""
        from core.dependencies import get_youtube_repo
        get_youtube_repo.cache_clear()
        await self.clear_home_cache()
        logger.info("YouTube settings change: singleton reset, home caches cleared")

    async def on_coverart_settings_changed(self) -> None:
        """Reset coverart singleton when settings change."""
        from core.dependencies import get_coverart_repository
        get_coverart_repository.cache_clear()
        logger.info("Coverart settings change: singleton reset")

    async def on_local_files_settings_changed(self) -> None:
        """Full cache reset when local files settings change."""
        await self.clear_local_files_cache()
        await self.clear_source_resolution_cache()
        logger.info("Local files settings change: caches reset")

    async def on_lidarr_settings_changed(self) -> None:
        """Full cache reset when Lidarr settings change."""
        from core.dependencies import get_library_db, get_home_service
        from infrastructure.cache.cache_keys import LIDARR_PREFIX

        await self.clear_home_cache()
        await self._cache.clear_prefix(LIDARR_PREFIX)

        library_db = get_library_db()
        await library_db.clear()

        try:
            home_service = get_home_service()
            home_service.clear_genre_disk_cache()
        except Exception:  # noqa: BLE001
            logger.debug("Genre disk cache cleanup skipped (home service unavailable)")

        logger.info("Lidarr settings change: home, lidarr, library and genre caches reset")

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
        except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to update Lidarr metadata profile {resolved_id}: {e}")
            raise ExternalServiceError(
                f"Failed to update Lidarr metadata profile: {e}"
            )

        logger.info(f"Updated Lidarr metadata profile '{result.get('name')}' (ID: {resolved_id})")
        return self._lidarr_profile_to_preferences(result)

    async def verify_navidrome(
        self, settings: NavidromeConnectionSettings
    ) -> NavidromeVerifyResult:
        try:
            from infrastructure.validators import validate_service_url
            validate_service_url(settings.navidrome_url, label="Navidrome URL")

            from repositories.navidrome_repository import NavidromeRepository

            NavidromeRepository.reset_circuit_breaker()

            app_settings = get_settings()
            http_client = get_http_client(app_settings)
            temp_cache = InMemoryCache(max_entries=100)

            temp_repo = NavidromeRepository(http_client=http_client, cache=temp_cache)

            password = settings.password
            if password == NAVIDROME_PASSWORD_MASK:
                raw = self._preferences_service.get_navidrome_connection_raw()
                password = raw.password

            temp_repo.configure(
                url=settings.navidrome_url,
                username=settings.username,
                password=password,
            )

            ok = await temp_repo.ping()
            if ok:
                return NavidromeVerifyResult(
                    valid=True, message="Connected to Navidrome successfully"
                )
            return NavidromeVerifyResult(
                valid=False,
                message="Navidrome didn't respond. Check the URL and credentials.",
            )
        except Exception as e:
            logger.exception("Failed to verify Navidrome connection: %s", e)
            return NavidromeVerifyResult(
                valid=False,
                message="Couldn't finish the connection test",
            )

    async def verify_youtube(
        self, settings: YouTubeConnectionSettings
    ) -> YouTubeVerifyResult:
        try:
            from repositories.youtube import YouTubeRepository

            app_settings = get_settings()
            http_client = get_http_client(app_settings)
            temp_repo = YouTubeRepository(
                http_client=http_client,
                api_key=settings.api_key.strip(),
                daily_quota_limit=settings.daily_quota_limit,
            )
            valid, message = await temp_repo.verify_api_key(settings.api_key.strip())
            return YouTubeVerifyResult(valid=valid, message=message)
        except Exception as e:
            logger.exception("Failed to verify YouTube connection: %s", e)
            return YouTubeVerifyResult(
                valid=False,
                message="Couldn't finish the connection test",
            )

    async def verify_lastfm(
        self, settings: LastFmConnectionSettings
    ) -> LastFmVerifyResult:
        try:
            from repositories.lastfm_repository import LastFmRepository

            app_settings = get_settings()
            http_client = get_http_client(app_settings)

            current = self._preferences_service.get_lastfm_connection()
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
                return LastFmVerifyResult(valid=False, message=message)

            if session_key:
                session_valid, session_message = await temp_repo.validate_session()
                if not session_valid:
                    return LastFmVerifyResult(
                        valid=False,
                        message=f"The API key looks good, but the saved session isn't valid: {session_message}",
                    )
                return LastFmVerifyResult(valid=True, message=session_message)

            return LastFmVerifyResult(valid=valid, message=message)
        except Exception as e:
            logger.exception("Failed to verify Last.fm connection: %s", e)
            return LastFmVerifyResult(
                valid=False, message="Couldn't finish the Last.fm connection test"
            )

    async def verify_plex(
        self, settings: PlexConnectionSettings
    ) -> PlexVerifyResult:
        try:
            from infrastructure.validators import validate_service_url
            validate_service_url(settings.plex_url, label="Plex URL")

            from repositories.plex_repository import PlexRepository

            PlexRepository.reset_circuit_breaker()

            app_settings = get_settings()
            http_client = get_http_client(app_settings)
            temp_cache = InMemoryCache(max_entries=100)

            token = settings.plex_token
            if token == PLEX_TOKEN_MASK:
                raw = self._preferences_service.get_plex_connection_raw()
                token = raw.plex_token

            client_id = self._preferences_service.get_setting("plex_client_id") or ""

            temp_repo = PlexRepository(http_client=http_client, cache=temp_cache)
            temp_repo.configure(
                url=settings.plex_url,
                token=token,
                client_id=client_id,
            )

            ok, message = await temp_repo.validate_connection()
            libs: list[tuple[str, str]] = []
            if ok:
                try:
                    sections = await temp_repo.get_music_libraries()
                    libs = [(s.key, s.title) for s in sections]
                except Exception:
                    logger.warning("Plex verify succeeded but library fetch failed")
            return PlexVerifyResult(valid=ok, message=message, libraries=libs)
        except Exception as e:
            logger.exception("Failed to verify Plex connection: %s", e)
            return PlexVerifyResult(
                valid=False,
                message="Couldn't finish the Plex connection test",
            )

    async def on_plex_settings_changed(self, enabled: bool = False) -> None:
        """Full cache/state reset when Plex settings change."""
        from repositories.plex_repository import PlexRepository
        from core.dependencies import (
            get_plex_repository, get_plex_library_service,
            get_plex_playback_service, get_home_service,
            get_home_charts_service, get_mbid_store,
        )
        PlexRepository.reset_circuit_breaker()
        get_plex_repository.cache_clear()
        get_plex_library_service.cache_clear()
        get_plex_playback_service.cache_clear()
        get_home_service.cache_clear()
        get_home_charts_service.cache_clear()
        mbid_store = get_mbid_store()
        await mbid_store.clear_plex_mbid_indexes()
        new_repo = get_plex_repository()
        await new_repo.clear_cache()
        await self.clear_home_cache()
        await self.clear_source_resolution_cache()
        if enabled:
            import asyncio
            from core.tasks import warm_plex_mbid_cache
            from core.task_registry import TaskRegistry
            registry = TaskRegistry.get_instance()
            if not registry.is_running("plex-mbid-warmup"):
                _plex_task = asyncio.create_task(warm_plex_mbid_cache())
                try:
                    registry.register("plex-mbid-warmup", _plex_task)
                except RuntimeError:
                    pass
        logger.info("Plex settings change: all caches/singletons reset")

    async def get_plex_libraries(self) -> list[tuple[str, str]]:
        raw = self._preferences_service.get_plex_connection_raw()
        if not raw.plex_url or not raw.plex_token:
            raise ValueError("Plex is not configured")

        from repositories.plex_repository import PlexRepository

        app_settings = get_settings()
        http_client = get_http_client(app_settings)
        temp_cache = InMemoryCache(max_entries=100)
        client_id = self._preferences_service.get_setting("plex_client_id") or ""
        temp_repo = PlexRepository(http_client=http_client, cache=temp_cache)
        temp_repo.configure(url=raw.plex_url, token=raw.plex_token, client_id=client_id)
        sections = await temp_repo.get_music_libraries()
        return [(s.key, s.title) for s in sections]

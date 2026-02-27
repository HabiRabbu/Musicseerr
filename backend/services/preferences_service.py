import json
import logging
import threading
from typing import Optional, TypeVar, Type
from pydantic import BaseModel
from api.v1.schemas.settings import (
    UserPreferences,
    LidarrSettings,
    LidarrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    YouTubeConnectionSettings,
    HomeSettings,
    LocalFilesConnectionSettings,
    LastFmConnectionSettings,
    ScrobbleSettings,
    PrimaryMusicSourceSettings,
    LASTFM_SECRET_MASK,
)
from api.v1.schemas.advanced_settings import AdvancedSettings
from core.config import Settings
from core.exceptions import ConfigurationError
from infrastructure.file_utils import atomic_write_json

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class PreferencesService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._config_path = settings.config_file_path
        self._config_cache: Optional[dict] = None
        self._cache_lock = threading.Lock()

    def _load_config(self) -> dict:
        with self._cache_lock:
            if self._config_cache is not None:
                return self._config_cache

            if not self._config_path.exists():
                self._config_cache = {}
                return self._config_cache

            try:
                with open(self._config_path, encoding='utf-8') as f:
                    self._config_cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self._config_cache = {}

            return self._config_cache

    def _save_config(self, config: dict) -> None:
        with self._cache_lock:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self._config_path, config)
            self._config_cache = config

    def _get_section(self, key: str, model: Type[T], default_factory: Optional[callable] = None) -> T:
        config = self._load_config()
        data = config.get(key, {})
        try:
            return model(**data) if data else (default_factory() if default_factory else model())
        except Exception as e:
            logger.error(f"Failed to parse {key}: {e}")
            return default_factory() if default_factory else model()

    def _save_section(self, key: str, value: BaseModel) -> None:
        config = self._load_config().copy()
        config[key] = value.model_dump()
        self._save_config(config)

    def get_preferences(self) -> UserPreferences:
        return self._get_section("user_preferences", UserPreferences)

    def save_preferences(self, preferences: UserPreferences) -> None:
        try:
            self._save_section("user_preferences", preferences)
            logger.info(f"Saved preferences to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            raise ConfigurationError(f"Failed to save preferences: {e}")

    def get_lidarr_settings(self) -> LidarrSettings:
        return self._get_section("lidarr_settings", LidarrSettings)

    def save_lidarr_settings(self, lidarr_settings: LidarrSettings) -> None:
        try:
            self._save_section("lidarr_settings", lidarr_settings)
            logger.info(f"Saved Lidarr settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save Lidarr settings: {e}")
            raise ConfigurationError(f"Failed to save Lidarr settings: {e}")

    def get_advanced_settings(self) -> AdvancedSettings:
        return self._get_section("advanced_settings", AdvancedSettings)

    def save_advanced_settings(self, advanced_settings: AdvancedSettings) -> None:
        try:
            self._save_section("advanced_settings", advanced_settings)
            logger.info(f"Saved advanced settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save advanced settings: {e}")
            raise ConfigurationError(f"Failed to save advanced settings: {e}")

    def get_lidarr_connection(self) -> LidarrConnectionSettings:
        config = self._load_config()
        return LidarrConnectionSettings(
            lidarr_url=config.get("lidarr_url", self._settings.lidarr_url),
            lidarr_api_key=config.get("lidarr_api_key", self._settings.lidarr_api_key),
            quality_profile_id=config.get("quality_profile_id", self._settings.quality_profile_id),
            metadata_profile_id=config.get("metadata_profile_id", self._settings.metadata_profile_id),
            root_folder_path=config.get("root_folder_path", self._settings.root_folder_path),
        )

    def save_lidarr_connection(self, settings: LidarrConnectionSettings) -> None:
        try:
            config = self._load_config().copy()
            config.update({
                "lidarr_url": settings.lidarr_url,
                "lidarr_api_key": settings.lidarr_api_key,
                "quality_profile_id": settings.quality_profile_id,
                "metadata_profile_id": settings.metadata_profile_id,
                "root_folder_path": settings.root_folder_path,
            })
            self._save_config(config)

            self._settings.lidarr_url = settings.lidarr_url
            self._settings.lidarr_api_key = settings.lidarr_api_key
            self._settings.quality_profile_id = settings.quality_profile_id
            self._settings.metadata_profile_id = settings.metadata_profile_id
            self._settings.root_folder_path = settings.root_folder_path

            logger.info(f"Saved Lidarr connection settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save Lidarr connection settings: {e}")
            raise ConfigurationError(f"Failed to save Lidarr connection settings: {e}")

    def get_jellyfin_connection(self) -> JellyfinConnectionSettings:
        config = self._load_config()
        jellyfin_data = config.get("jellyfin_settings", {})
        return JellyfinConnectionSettings(
            jellyfin_url=jellyfin_data.get("jellyfin_url", config.get("jellyfin_url", self._settings.jellyfin_url)),
            api_key=jellyfin_data.get("api_key", ""),
            user_id=jellyfin_data.get("user_id", ""),
            enabled=jellyfin_data.get("enabled", False),
        )

    def save_jellyfin_connection(self, settings: JellyfinConnectionSettings) -> None:
        try:
            config = self._load_config().copy()
            config["jellyfin_url"] = settings.jellyfin_url
            config["jellyfin_settings"] = {
                "jellyfin_url": settings.jellyfin_url,
                "api_key": settings.api_key,
                "user_id": settings.user_id,
                "enabled": settings.enabled,
            }
            self._save_config(config)

            self._settings.jellyfin_url = settings.jellyfin_url

            logger.info(f"Saved Jellyfin connection settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save Jellyfin connection settings: {e}")
            raise ConfigurationError(f"Failed to save Jellyfin connection settings: {e}")

    def get_listenbrainz_connection(self) -> ListenBrainzConnectionSettings:
        config = self._load_config()
        lb_data = config.get("listenbrainz_settings", {})
        return ListenBrainzConnectionSettings(
            username=lb_data.get("username", ""),
            user_token=lb_data.get("user_token", ""),
            enabled=lb_data.get("enabled", False),
        )

    def save_listenbrainz_connection(self, settings: ListenBrainzConnectionSettings) -> None:
        try:
            config = self._load_config().copy()
            config["listenbrainz_settings"] = {
                "username": settings.username,
                "user_token": settings.user_token,
                "enabled": settings.enabled,
            }
            self._save_config(config)

            logger.info(f"Saved ListenBrainz connection settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save ListenBrainz connection settings: {e}")
            raise ConfigurationError(f"Failed to save ListenBrainz connection settings: {e}")

    def get_youtube_connection(self) -> YouTubeConnectionSettings:
        config = self._load_config()
        yt_data = config.get("youtube_settings", {})
        return YouTubeConnectionSettings(
            api_key=yt_data.get("api_key", ""),
            enabled=yt_data.get("enabled", False),
            daily_quota_limit=yt_data.get("daily_quota_limit", 80),
        )

    def save_youtube_connection(self, settings: YouTubeConnectionSettings) -> None:
        try:
            config = self._load_config().copy()
            config["youtube_settings"] = {
                "api_key": settings.api_key,
                "enabled": settings.enabled,
                "daily_quota_limit": settings.daily_quota_limit,
            }
            self._save_config(config)
            logger.info(f"Saved YouTube connection settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save YouTube connection settings: {e}")
            raise ConfigurationError(f"Failed to save YouTube connection settings: {e}")

    def get_home_settings(self) -> HomeSettings:
        return self._get_section("home_settings", HomeSettings)

    def save_home_settings(self, settings: HomeSettings) -> None:
        try:
            self._save_section("home_settings", settings)
            logger.info(f"Saved home settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save home settings: {e}")
            raise ConfigurationError(f"Failed to save home settings: {e}")

    def get_local_files_connection(self) -> LocalFilesConnectionSettings:
        return self._get_section("local_files_settings", LocalFilesConnectionSettings)

    def save_local_files_connection(self, settings: LocalFilesConnectionSettings) -> None:
        try:
            self._save_section("local_files_settings", settings)
            logger.info("Saved local files settings to %s", self._config_path)
        except Exception as e:
            logger.error("Failed to save local files settings: %s", e)
            raise ConfigurationError(f"Failed to save local files settings: {e}")

    def get_lastfm_connection(self) -> LastFmConnectionSettings:
        return self._get_section("lastfm_settings", LastFmConnectionSettings)

    def save_lastfm_connection(self, settings: LastFmConnectionSettings) -> None:
        try:
            current = self.get_lastfm_connection()

            api_key = settings.api_key.strip()
            shared_secret = settings.shared_secret
            if shared_secret.startswith(LASTFM_SECRET_MASK):
                shared_secret = current.shared_secret
            else:
                shared_secret = shared_secret.strip()

            session_key = settings.session_key
            if session_key.startswith(LASTFM_SECRET_MASK):
                session_key = current.session_key
            else:
                session_key = session_key.strip()

            username = settings.username.strip()
            enabled = settings.enabled
            if not api_key or not shared_secret:
                enabled = False
                session_key = ""
                username = ""

            resolved = LastFmConnectionSettings(
                api_key=api_key,
                shared_secret=shared_secret,
                session_key=session_key,
                username=username,
                enabled=enabled,
            )
            self._save_section("lastfm_settings", resolved)
            logger.info("Saved Last.fm connection settings to %s", self._config_path)
        except Exception as e:
            logger.error("Failed to save Last.fm connection settings: %s", e)
            raise ConfigurationError(f"Failed to save Last.fm connection settings: {e}")

    def is_lastfm_enabled(self) -> bool:
        settings = self.get_lastfm_connection()
        return settings.enabled and bool(settings.api_key) and bool(settings.shared_secret)

    def get_scrobble_settings(self) -> ScrobbleSettings:
        return self._get_section("scrobble_settings", ScrobbleSettings)

    def save_scrobble_settings(self, settings: ScrobbleSettings) -> None:
        try:
            self._save_section("scrobble_settings", settings)
            logger.info("Saved scrobble settings to %s", self._config_path)
        except Exception as e:
            logger.error("Failed to save scrobble settings: %s", e)
            raise ConfigurationError(f"Failed to save scrobble settings: {e}")

    def get_primary_music_source(self) -> PrimaryMusicSourceSettings:
        return self._get_section("primary_music_source", PrimaryMusicSourceSettings)

    def save_primary_music_source(self, settings: PrimaryMusicSourceSettings) -> None:
        try:
            self._save_section("primary_music_source", settings)
            logger.info("Saved primary music source to %s", self._config_path)
        except Exception as e:
            logger.error("Failed to save primary music source: %s", e)
            raise ConfigurationError(f"Failed to save primary music source: {e}")

import json
import logging
import threading
from typing import Optional, TypeVar, Type
from pydantic import BaseModel
from api.v1.schemas.settings import (
    UserPreferences,
    LidarrSettings,
    LidarrConnectionSettings,
    SoularrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    YouTubeConnectionSettings,
    HomeSettings
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

    def get_soularr_connection(self) -> SoularrConnectionSettings:
        config = self._load_config()
        return SoularrConnectionSettings(
            soularr_url=config.get("soularr_url", self._settings.soularr_url),
            soularr_api_key=config.get("soularr_api_key", self._settings.soularr_api_key),
            trigger_soularr=config.get("trigger_soularr", self._settings.trigger_soularr),
        )

    def save_soularr_connection(self, settings: SoularrConnectionSettings) -> None:
        try:
            config = self._load_config().copy()
            config.update({
                "soularr_url": settings.soularr_url,
                "soularr_api_key": settings.soularr_api_key,
                "trigger_soularr": settings.trigger_soularr,
            })
            self._save_config(config)

            self._settings.soularr_url = settings.soularr_url
            self._settings.soularr_api_key = settings.soularr_api_key
            self._settings.trigger_soularr = settings.trigger_soularr

            logger.info(f"Saved Soularr connection settings to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save Soularr connection settings: {e}")
            raise ConfigurationError(f"Failed to save Soularr connection settings: {e}")

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
        )

    def save_youtube_connection(self, settings: YouTubeConnectionSettings) -> None:
        try:
            config = self._load_config().copy()
            config["youtube_settings"] = {
                "api_key": settings.api_key,
                "enabled": settings.enabled,
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

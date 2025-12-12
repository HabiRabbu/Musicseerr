import json
import logging
import time
from typing import Optional
from api.v1.schemas.settings import (
    UserPreferences, 
    LidarrSettings,
    LidarrConnectionSettings,
    SoularrConnectionSettings,
    JellyfinConnectionSettings,
    ListenBrainzConnectionSettings,
    HomeSettings
)
from api.v1.schemas.advanced_settings import AdvancedSettings
from core.config import Settings
from core.exceptions import ConfigurationError
from infrastructure.file_utils import atomic_write_json

logger = logging.getLogger(__name__)


class PreferencesService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._config_path = settings.config_file_path
        self._cached_preferences: Optional[UserPreferences] = None
        self._cached_lidarr_settings: Optional[LidarrSettings] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 60.0
    
    def get_preferences(self) -> UserPreferences:
        now = time.time()
        
        if self._cached_preferences is not None and (now - self._cache_timestamp) < self._cache_ttl:
            return self._cached_preferences
        
        try:
            if not self._config_path.exists():
                prefs = UserPreferences()
            else:
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
                
                prefs_data = config.get("user_preferences", {})
                prefs = UserPreferences(**prefs_data)
            
            self._cached_preferences = prefs
            self._cache_timestamp = now
            return prefs
        
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return UserPreferences()
    
    def save_preferences(self, preferences: UserPreferences) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config["user_preferences"] = preferences.model_dump()
            
            atomic_write_json(self._config_path, config)
            
            self._cached_preferences = preferences
            self._cache_timestamp = 0 
            
            logger.info(f"Saved preferences to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            raise ConfigurationError(f"Failed to save preferences: {e}")
    
    def get_lidarr_settings(self) -> LidarrSettings:
        try:
            if not self._config_path.exists():
                return LidarrSettings()
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            lidarr_data = config.get("lidarr_settings", {})
            return LidarrSettings(**lidarr_data)
        
        except Exception as e:
            logger.error(f"Failed to get Lidarr settings: {e}")
            return LidarrSettings()
    
    def save_lidarr_settings(self, lidarr_settings: LidarrSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config["lidarr_settings"] = lidarr_settings.model_dump()
            
            atomic_write_json(self._config_path, config)
            
            self._cached_lidarr_settings = lidarr_settings
            
            logger.info(f"Saved Lidarr settings to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save Lidarr settings: {e}")
            raise ConfigurationError(f"Failed to save Lidarr settings: {e}")
    
    def get_advanced_settings(self) -> AdvancedSettings:
        try:
            if not self._config_path.exists():
                return AdvancedSettings()
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            advanced_data = config.get("advanced_settings", {})
            return AdvancedSettings(**advanced_data)
        
        except Exception as e:
            logger.error(f"Failed to get advanced settings: {e}")
            return AdvancedSettings()
    
    def save_advanced_settings(self, advanced_settings: AdvancedSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config["advanced_settings"] = advanced_settings.model_dump()
            
            atomic_write_json(self._config_path, config)
            
            logger.info(f"Saved advanced settings to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save advanced settings: {e}")
            raise ConfigurationError(f"Failed to save advanced settings: {e}")
    
    def get_lidarr_connection(self) -> LidarrConnectionSettings:
        try:
            if not self._config_path.exists():
                return LidarrConnectionSettings(
                    lidarr_url=self._settings.lidarr_url,
                    lidarr_api_key=self._settings.lidarr_api_key,
                    quality_profile_id=self._settings.quality_profile_id,
                    metadata_profile_id=self._settings.metadata_profile_id,
                    root_folder_path=self._settings.root_folder_path,
                )
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            return LidarrConnectionSettings(
                lidarr_url=config.get("lidarr_url", self._settings.lidarr_url),
                lidarr_api_key=config.get("lidarr_api_key", self._settings.lidarr_api_key),
                quality_profile_id=config.get("quality_profile_id", self._settings.quality_profile_id),
                metadata_profile_id=config.get("metadata_profile_id", self._settings.metadata_profile_id),
                root_folder_path=config.get("root_folder_path", self._settings.root_folder_path),
            )
        
        except Exception as e:
            logger.error(f"Failed to get Lidarr connection settings: {e}")
            return LidarrConnectionSettings()
    
    def save_lidarr_connection(self, settings: LidarrConnectionSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config.update({
                "lidarr_url": settings.lidarr_url,
                "lidarr_api_key": settings.lidarr_api_key,
                "quality_profile_id": settings.quality_profile_id,
                "metadata_profile_id": settings.metadata_profile_id,
                "root_folder_path": settings.root_folder_path,
            })
            
            atomic_write_json(self._config_path, config)
            
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
        try:
            if not self._config_path.exists():
                return SoularrConnectionSettings(
                    soularr_url=self._settings.soularr_url,
                    soularr_api_key=self._settings.soularr_api_key,
                    trigger_soularr=self._settings.trigger_soularr,
                )
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            return SoularrConnectionSettings(
                soularr_url=config.get("soularr_url", self._settings.soularr_url),
                soularr_api_key=config.get("soularr_api_key", self._settings.soularr_api_key),
                trigger_soularr=config.get("trigger_soularr", self._settings.trigger_soularr),
            )
        
        except Exception as e:
            logger.error(f"Failed to get Soularr connection settings: {e}")
            return SoularrConnectionSettings()
    
    def save_soularr_connection(self, settings: SoularrConnectionSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config.update({
                "soularr_url": settings.soularr_url,
                "soularr_api_key": settings.soularr_api_key,
                "trigger_soularr": settings.trigger_soularr,
            })
            
            atomic_write_json(self._config_path, config)
            
            self._settings.soularr_url = settings.soularr_url
            self._settings.soularr_api_key = settings.soularr_api_key
            self._settings.trigger_soularr = settings.trigger_soularr
            
            logger.info(f"Saved Soularr connection settings to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save Soularr connection settings: {e}")
            raise ConfigurationError(f"Failed to save Soularr connection settings: {e}")
    
    def get_jellyfin_connection(self) -> JellyfinConnectionSettings:
        try:
            if not self._config_path.exists():
                return JellyfinConnectionSettings(
                    jellyfin_url=self._settings.jellyfin_url,
                )
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            jellyfin_data = config.get("jellyfin_settings", {})
            return JellyfinConnectionSettings(
                jellyfin_url=jellyfin_data.get("jellyfin_url", config.get("jellyfin_url", self._settings.jellyfin_url)),
                api_key=jellyfin_data.get("api_key", ""),
                user_id=jellyfin_data.get("user_id", ""),
                enabled=jellyfin_data.get("enabled", False),
            )
        
        except Exception as e:
            logger.error(f"Failed to get Jellyfin connection settings: {e}")
            return JellyfinConnectionSettings()
    
    def save_jellyfin_connection(self, settings: JellyfinConnectionSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config["jellyfin_url"] = settings.jellyfin_url
            config["jellyfin_settings"] = {
                "jellyfin_url": settings.jellyfin_url,
                "api_key": settings.api_key,
                "user_id": settings.user_id,
                "enabled": settings.enabled,
            }
            
            atomic_write_json(self._config_path, config)
            
            self._settings.jellyfin_url = settings.jellyfin_url
            
            logger.info(f"Saved Jellyfin connection settings to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save Jellyfin connection settings: {e}")
            raise ConfigurationError(f"Failed to save Jellyfin connection settings: {e}")
    
    def get_listenbrainz_connection(self) -> ListenBrainzConnectionSettings:
        try:
            if not self._config_path.exists():
                return ListenBrainzConnectionSettings()
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            lb_data = config.get("listenbrainz_settings", {})
            return ListenBrainzConnectionSettings(
                username=lb_data.get("username", ""),
                user_token=lb_data.get("user_token", ""),
                enabled=lb_data.get("enabled", False),
            )
        
        except Exception as e:
            logger.error(f"Failed to get ListenBrainz connection settings: {e}")
            return ListenBrainzConnectionSettings()
    
    def save_listenbrainz_connection(self, settings: ListenBrainzConnectionSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config["listenbrainz_settings"] = {
                "username": settings.username,
                "user_token": settings.user_token,
                "enabled": settings.enabled,
            }
            
            atomic_write_json(self._config_path, config)
            
            logger.info(f"Saved ListenBrainz connection settings to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save ListenBrainz connection settings: {e}")
            raise ConfigurationError(f"Failed to save ListenBrainz connection settings: {e}")
    
    def get_home_settings(self) -> HomeSettings:
        try:
            if not self._config_path.exists():
                return HomeSettings()
            
            with open(self._config_path, encoding='utf-8') as f:
                config = json.load(f)
            
            home_data = config.get("home_settings", {})
            return HomeSettings(**home_data)
        
        except Exception as e:
            logger.error(f"Failed to get home settings: {e}")
            return HomeSettings()
    
    def save_home_settings(self, settings: HomeSettings) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    config = json.load(f)
            
            config["home_settings"] = settings.model_dump()
            
            atomic_write_json(self._config_path, config)
            
            logger.info(f"Saved home settings to {self._config_path}")
        
        except Exception as e:
            logger.error(f"Failed to save home settings: {e}")
            raise ConfigurationError(f"Failed to save home settings: {e}")

import json
import logging
from typing import Optional
from api.v1.schemas.settings import UserPreferences
from core.config import Settings
from core.exceptions import ConfigurationError
from infrastructure.file_utils import atomic_write_json

logger = logging.getLogger(__name__)


class PreferencesService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._config_path = settings.config_file_path
        self._cached_preferences: Optional[UserPreferences] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 60.0  # Cache for 60 seconds
    
    def get_preferences(self) -> UserPreferences:
        """Get preferences with memoization to avoid repeated file I/O."""
        import time
        
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
            
            # Cache the result
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

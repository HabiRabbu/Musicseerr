from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import logging
from infrastructure.file_utils import atomic_write_json

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )
    
    lidarr_url: str = Field(default="http://lidarr:8686")
    lidarr_api_key: str = Field(default="")
    
    soularr_url: str = Field(default="http://soularr:8181")
    soularr_api_key: str = Field(default="")
    trigger_soularr: bool = Field(default=False)
    
    jellyfin_url: str = Field(default="http://jellyfin:8096")
    
    quality_profile_id: int = Field(default=1)
    metadata_profile_id: int = Field(default=1)
    root_folder_path: str = Field(default="/music")
    
    port: int = Field(default=8688)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    cache_ttl_default: int = Field(default=60)
    cache_ttl_artist: int = Field(default=3600)
    cache_ttl_album: int = Field(default=3600)
    cache_ttl_covers: int = Field(default=86400, description="Cover cache TTL in seconds (default: 24 hours)")
    cache_cleanup_interval: int = Field(default=300)
    
    cache_dir: Path = Field(default=Path("/app/cache"), description="Root directory for all cache files")
    library_db_path: Path = Field(default=Path("/app/cache/library.db"), description="SQLite library database path")
    cover_cache_max_size_mb: int = Field(default=500, description="Maximum cover cache size in MB")
    metadata_cache_max_entries: int = Field(default=100, description="Maximum entries in RAM metadata cache")
    
    http_timeout: float = Field(default=10.0)
    http_connect_timeout: float = Field(default=5.0)
    http_max_connections: int = Field(default=200)
    http_max_keepalive: int = Field(default=50)
    
    config_file_path: Path = Field(default=Path("/app/config/config.json"))
    
    @field_validator("lidarr_url", "soularr_url", "jellyfin_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return v.rstrip("/")
    
    def load_from_file(self) -> None:
        if not self.config_file_path.exists():
            self._create_default_config()
            return
        
        try:
            with open(self.config_file_path, encoding='utf-8') as f:
                config_data = json.load(f)
            
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            logger.info(f"Loaded configuration from {self.config_file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise ValueError(f"Config file is not valid JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _create_default_config(self) -> None:
        self.config_file_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "lidarr_url": self.lidarr_url,
            "lidarr_api_key": self.lidarr_api_key,
            "soularr_url": self.soularr_url,
            "soularr_api_key": self.soularr_api_key,
            "jellyfin_url": self.jellyfin_url,
            "trigger_soularr": self.trigger_soularr,
            "quality_profile_id": self.quality_profile_id,
            "metadata_profile_id": self.metadata_profile_id,
            "root_folder_path": self.root_folder_path,
            "port": self.port,
            "user_preferences": {
                "primary_types": ["album", "ep", "single"],
                "secondary_types": ["studio"],
                "release_statuses": ["official"],
            },
        }
        atomic_write_json(self.config_file_path, config_data)
        logger.info(f"Created default config at {self.config_file_path}")
    
    def save_to_file(self) -> None:
        try:
            self.config_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            config_data = {}
            if self.config_file_path.exists():
                with open(self.config_file_path, encoding='utf-8') as f:
                    config_data = json.load(f)
            
            config_data.update({
                "lidarr_url": self.lidarr_url,
                "lidarr_api_key": self.lidarr_api_key,
                "soularr_url": self.soularr_url,
                "soularr_api_key": self.soularr_api_key,
                "jellyfin_url": self.jellyfin_url,
                "trigger_soularr": self.trigger_soularr,
                "quality_profile_id": self.quality_profile_id,
                "metadata_profile_id": self.metadata_profile_id,
                "root_folder_path": self.root_folder_path,
                "port": self.port,
            })
            
            atomic_write_json(self.config_file_path, config_data)
            
            logger.info(f"Saved config to {self.config_file_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.load_from_file()
    return _settings

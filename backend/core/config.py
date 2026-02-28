from pathlib import Path
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Self
import logging
import msgspec
from infrastructure.file_utils import atomic_write_json, read_json

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
    
    jellyfin_url: str = Field(default="http://jellyfin:8096")
    
    contact_email: str = Field(
        default="contact@musicseerr.com",
        description="Contact email for MusicBrainz API User-Agent. Override with your own if desired."
    )
    
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
    
    http_timeout: float = Field(default=10.0)
    http_connect_timeout: float = Field(default=5.0)
    http_max_connections: int = Field(default=200)
    http_max_keepalive: int = Field(default=50)
    
    config_file_path: Path = Field(default=Path("/app/config/config.json"))
    
    @field_validator("lidarr_url", "jellyfin_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode='after')
    def validate_config(self) -> Self:
        errors = []
        warnings = []

        for url_field in ['lidarr_url', 'jellyfin_url']:
            url = getattr(self, url_field, '')
            if url and not url.startswith(('http://', 'https://')):
                errors.append(f"{url_field} must start with http:// or https://")

        if self.http_max_connections < self.http_max_keepalive * 2:
            errors.append(
                f"http_max_connections ({self.http_max_connections}) should be "
                f"at least 2x http_max_keepalive ({self.http_max_keepalive})"
            )

        if not self.lidarr_api_key:
            warnings.append("LIDARR_API_KEY is not set - Lidarr features will not work")

        if errors:
            logger.warning(f"Configuration validation warnings: {'; '.join(errors)}")
        
        for warning in warnings:
            logger.warning(warning)

        return self
    
    def get_user_agent(self) -> str:
        return f"Musicseerr/1.0 ({self.contact_email}; https://www.musicseerr.com)"

    def load_from_file(self) -> None:
        if not self.config_file_path.exists():
            self._create_default_config()
            return
        
        try:
            config_data = read_json(self.config_file_path, default={})
            if not isinstance(config_data, dict):
                raise ValueError("Config file JSON root must be an object")
            
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            logger.info(f"Loaded configuration from {self.config_file_path}")
        except msgspec.DecodeError as e:
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
            "jellyfin_url": self.jellyfin_url,
            "contact_email": self.contact_email,
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
                loaded = read_json(self.config_file_path, default={})
                config_data = loaded if isinstance(loaded, dict) else {}
            
            config_data.update({
                "lidarr_url": self.lidarr_url,
                "lidarr_api_key": self.lidarr_api_key,
                "jellyfin_url": self.jellyfin_url,
                "contact_email": self.contact_email,
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

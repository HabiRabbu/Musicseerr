"""Configuration management for Musicseerr."""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("/app/config/config.json")

DEFAULT_CONFIG = {
    "lidarr_url": "http://lidarr:8686",
    "lidarr_api_key": "",
    "soularr_url": "http://soularr:8181",
    "soularr_api_key": "",
    "jellyfin_url": "http://jellyfin:8096",
    "trigger_soularr": True,
    "quality_profile_id": 1,
    "metadata_profile_id": 1,
    "root_folder_path": "/music",
    "port": 8688,
}


def _create_default_config() -> None:
    """Create default config file if it doesn't exist."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    logger.info(f"Created default config at {CONFIG_PATH}")


def load_config() -> dict[str, Any]:
    """Load configuration from file, creating default if needed."""
    try:
        if not CONFIG_PATH.exists():
            _create_default_config()
        
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        
        # Merge with defaults for any missing keys
        return {**DEFAULT_CONFIG, **config}
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise ValueError(f"Config file is not valid JSON: {e}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise


CONFIG = load_config()

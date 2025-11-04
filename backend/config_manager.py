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
    "user_preferences": {
        "primary_types": ["album", "ep", "single"],
        "secondary_types": ["studio"],
        "release_statuses": ["official"],
    },
}


def _create_default_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    logger.info(f"Created default config at {CONFIG_PATH}")


def load_config() -> dict[str, Any]:
    try:
        if not CONFIG_PATH.exists():
            _create_default_config()
        
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        
        return {**DEFAULT_CONFIG, **config}
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise ValueError(f"Config file is not valid JSON: {e}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise


CONFIG = load_config()


def save_config(config: dict[str, Any]) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Saved config to {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise


def get_user_preferences() -> dict[str, Any]:
    config = load_config()
    return config.get("user_preferences", DEFAULT_CONFIG["user_preferences"])


def save_user_preferences(preferences: dict[str, Any]) -> None:
    config = load_config()
    config["user_preferences"] = preferences
    save_config(config)
    global CONFIG
    CONFIG = config


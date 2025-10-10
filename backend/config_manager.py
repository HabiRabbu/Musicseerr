import json
from pathlib import Path

CONFIG_PATH = Path("/app/config/config.json")
DEFAULT_CONFIG = {
    "lidarr_url": "http://lidarr:8686",
    "lidarr_api_key": "",
    "soularr_url": "http://soularr:8181",
    "soularr_api_key": "",
    "jellyfin_url": "http://jellyfin:8096",
    "trigger_soularr": True,
    "port": 8688
}


def load_config() -> dict:
    """
    Loads configuration from /app/config/config.json.
    Creates it automatically if missing, using DEFAULT_CONFIG.
    """
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        print("Created default config at /app/config/config.json")

    with open(CONFIG_PATH) as f:
        return json.load(f)


CONFIG = load_config()

from typing import Any
from config_manager import CONFIG


def get_auth_headers() -> dict[str, str]:
    return {
        "X-Api-Key": CONFIG.get("lidarr_api_key", ""),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


class ApiError(Exception):
    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(message)

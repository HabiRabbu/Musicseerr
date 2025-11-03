"""Common utilities and error classes."""
from typing import Any
from config_manager import CONFIG


class ApiError(Exception):
    """Custom exception for API-related errors."""
    
    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


def get_auth_headers() -> dict[str, str]:
    """Generate authentication headers for Lidarr API."""
    return {
        "X-Api-Key": CONFIG.get("lidarr_api_key", ""),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

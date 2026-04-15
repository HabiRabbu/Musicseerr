"""Auth service provider."""

from ._registry import singleton
from core.config import get_settings
from services.auth_service import AuthService


@singleton
def get_auth_service() -> AuthService:
    settings = get_settings()
    config_dir = settings.config_file_path.parent
    return AuthService(config_dir)

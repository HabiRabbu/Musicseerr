"""Auth dependency providers, wired into the singleton DI system."""

from __future__ import annotations

from core.config import get_settings
from infrastructure.persistence.auth_store import AuthStore

from ._registry import singleton
from .cache_providers import get_persistence_write_lock


@singleton
def get_auth_store() -> AuthStore:
    settings = get_settings()
    lock = get_persistence_write_lock()
    return AuthStore(db_path = settings.library_db_path, write_lock = lock)


@singleton
def get_auth_service() -> "AuthService":
    from services.auth_service import AuthService
    return AuthService(get_auth_store())

"""Optional authentication service.

Users are stored in /app/config/users.json.
Auth can be toggled on/off via settings without losing user accounts.
When disabled, every request is allowed through unchanged.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
from pathlib import Path
from typing import Optional

import bcrypt
import jwt

from infrastructure.file_utils import atomic_write_json, read_json

logger = logging.getLogger(__name__)

_TOKEN_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    def __init__(self, config_dir: Path):
        self._users_path = config_dir / "users.json"
        self._settings_path = config_dir / "auth_settings.json"
        self._lock = threading.Lock()
        self._jwt_secret: Optional[str] = None

    # ── JWT secret ────────────────────────────────────────────────────────────

    def _get_jwt_secret(self) -> str:
        if self._jwt_secret:
            return self._jwt_secret
        secret_path = self._users_path.parent / "jwt_secret.txt"
        if secret_path.exists():
            self._jwt_secret = secret_path.read_text().strip()
        else:
            self._jwt_secret = secrets.token_hex(32)
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            secret_path.write_text(self._jwt_secret)
        return self._jwt_secret

    # ── Auth enabled flag ─────────────────────────────────────────────────────

    def is_auth_enabled(self) -> bool:
        try:
            data = read_json(self._settings_path, default={})
            return bool(data.get("enabled", False))
        except Exception:  # noqa: BLE001
            return False

    def set_auth_enabled(self, enabled: bool) -> None:
        data: dict = {}
        if self._settings_path.exists():
            try:
                data = read_json(self._settings_path, default={})
            except Exception:  # noqa: BLE001
                pass
        data["enabled"] = enabled
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._settings_path, data)

    # ── User management ───────────────────────────────────────────────────────

    def _load_users(self) -> list[dict]:
        try:
            data = read_json(self._users_path, default={})
            return data.get("users", [])
        except Exception:  # noqa: BLE001
            return []

    def _save_users(self, users: list[dict]) -> None:
        self._users_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._users_path, {"users": users})

    def user_count(self) -> int:
        return len(self._load_users())

    def setup_required(self) -> bool:
        """True when auth is enabled but no accounts exist yet."""
        return self.is_auth_enabled() and self.user_count() == 0

    def create_user(self, username: str, password: str, role: str = "admin") -> None:
        with self._lock:
            users = self._load_users()
            if any(u["username"].lower() == username.lower() for u in users):
                raise ValueError("Username already taken")
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            users.append({"username": username, "password_hash": password_hash, "role": role})
            self._save_users(users)

    def _find_user(self, username: str) -> Optional[dict]:
        for u in self._load_users():
            if u["username"].lower() == username.lower() and not u.get("auth_provider"):
                return u
        return None

    def _find_plex_user(self, plex_username: str) -> Optional[dict]:
        for u in self._load_users():
            if u["username"].lower() == plex_username.lower() and u.get("auth_provider") == "plex":
                return u
        return None

    def create_or_get_emby_user(self, emby_username: str) -> dict:
        """Return existing Emby-linked account or create one with role 'user'."""
        with self._lock:
            for u in self._load_users():
                if u["username"].lower() == emby_username.lower() and u.get("auth_provider") == "emby":
                    return u
            user: dict = {
                "username": emby_username,
                "password_hash": "",
                "role": "user",
                "auth_provider": "emby",
            }
            users = self._load_users()
            users.append(user)
            self._save_users(users)
            return user

    def create_or_get_plex_user(self, plex_username: str) -> dict:
        """Return existing Plex-linked account or create one with role 'user'."""
        with self._lock:
            existing = self._find_plex_user(plex_username)
            if existing:
                return existing
            user: dict = {
                "username": plex_username,
                "password_hash": "",
                "role": "user",
                "auth_provider": "plex",
            }
            users = self._load_users()
            users.append(user)
            self._save_users(users)
            return user

    def get_all_users(self) -> list[dict]:
        """Return all users, scrubbing password hashes."""
        return [
            {
                "username": u["username"],
                "role": u.get("role", "user"),
                "auth_provider": u.get("auth_provider"),
                "can_request": u.get("can_request", True),
                "request_quota": u.get("request_quota"),
                "quota_days": u.get("quota_days"),
            }
            for u in self._load_users()
        ]

    def update_user(
        self,
        username: str,
        *,
        role: Optional[str] = None,
        can_request: Optional[bool] = None,
        request_quota: Optional[int] = None,
        quota_days: Optional[int] = None,
        clear_quota: bool = False,
    ) -> bool:
        """Update mutable fields on a user. Returns False if user not found."""
        with self._lock:
            users = self._load_users()
            for u in users:
                if u["username"].lower() == username.lower():
                    if role is not None:
                        u["role"] = role
                    if can_request is not None:
                        u["can_request"] = can_request
                    if clear_quota:
                        u.pop("request_quota", None)
                        u.pop("quota_days", None)
                    else:
                        if request_quota is not None:
                            u["request_quota"] = request_quota
                        if quota_days is not None:
                            u["quota_days"] = quota_days
                    self._save_users(users)
                    return True
            return False

    def delete_user(self, username: str) -> bool:
        """Remove a user. Returns False if not found."""
        with self._lock:
            users = self._load_users()
            new_users = [u for u in users if u["username"].lower() != username.lower()]
            if len(new_users) == len(users):
                return False
            self._save_users(new_users)
            return True

    def get_default_request_settings(self) -> dict:
        try:
            data = read_json(self._settings_path, default={})
            return data.get("request_defaults", {"quota": 20, "quota_days": 7, "can_request": True})
        except Exception:  # noqa: BLE001
            return {"quota": 20, "quota_days": 7, "can_request": True}

    def set_default_request_settings(self, quota: Optional[int], quota_days: int, can_request: bool) -> None:
        data: dict = {}
        if self._settings_path.exists():
            try:
                data = read_json(self._settings_path, default={})
            except Exception:  # noqa: BLE001
                pass
        data["request_defaults"] = {"quota": quota, "quota_days": quota_days, "can_request": can_request}
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._settings_path, data)

    def get_effective_request_settings(self, username: str) -> tuple[bool, Optional[int], int]:
        """Return (can_request, quota_limit, quota_days). quota_limit=None means unlimited."""
        user = None
        for u in self._load_users():
            if u["username"].lower() == username.lower():
                user = u
                break

        if not user:
            return True, None, 7

        if user.get("role") == "admin":
            return True, None, 7

        defaults = self.get_default_request_settings()
        can_request = user.get("can_request", defaults.get("can_request", True))
        quota = user.get("request_quota", defaults.get("quota"))  # None = unlimited
        quota_days = user.get("quota_days") or defaults.get("quota_days", 7)
        return bool(can_request), quota, int(quota_days)

    def verify_password(self, username: str, password: str) -> Optional[dict]:
        user = self._find_user(username)
        if not user:
            return None
        stored = user.get("password_hash", "")
        try:
            if bcrypt.checkpw(password.encode(), stored.encode()):
                return user
        except Exception:  # noqa: BLE001
            pass
        return None

    # ── JWT ───────────────────────────────────────────────────────────────────

    def create_token(self, username: str, role: str) -> str:
        import datetime

        payload = {
            "sub": username,
            "role": role,
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=_TOKEN_EXPIRE_DAYS),
        }
        return jwt.encode(payload, self._get_jwt_secret(), algorithm=_TOKEN_ALGORITHM)

    def validate_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, self._get_jwt_secret(), algorithms=[_TOKEN_ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.debug("JWT expired")
        except jwt.InvalidTokenError as e:
            logger.debug("Invalid JWT: %s", e)
        return None

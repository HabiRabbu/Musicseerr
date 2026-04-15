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
            if u["username"].lower() == username.lower():
                return u
        return None

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

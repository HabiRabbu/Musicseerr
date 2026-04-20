"""Msgspec schemas for auth endpoints."""

from __future__ import annotations

import msgspec


class SetupStatusResponse(msgspec.Struct, frozen = True):
    required: bool


class SetupRequest(msgspec.Struct, frozen = True):
    display_name: str
    email: str
    password: str


class CreateUserRequest(msgspec.Struct, frozen = True):
    display_name: str
    email: str
    password: str
    role: str = "user"


class LoginRequest(msgspec.Struct, frozen = True):
    email: str
    password: str


class UserResponse(msgspec.Struct, frozen = True):
    id: str
    display_name: str
    role: str
    email: str | None = None
    avatar_url: str | None = None


class AuthResponse(msgspec.Struct, frozen = True):
    token: str
    user: UserResponse


class SessionResponse(msgspec.Struct, frozen = True):
    id: str
    issued_at: str
    expires_at: str
    last_seen_at: str
    user_agent: str | None = None


class SessionListResponse(msgspec.Struct, frozen = True):
    sessions: list[SessionResponse]


class UserListResponse(msgspec.Struct, frozen = True):
    users: list[UserResponse]
    total: int


class SetRoleRequest(msgspec.Struct, frozen = True):
    role: str


def user_to_response(user) -> UserResponse:
    return UserResponse(
        id = user.id,
        display_name = user.display_name,
        role = user.role,
        email = user.email,
        avatar_url = user.avatar_url,
    )


def session_to_response(token) -> SessionResponse:
    return SessionResponse(
        id = token.id,
        issued_at = token.issued_at,
        expires_at = token.expires_at,
        last_seen_at = token.last_seen_at,
        user_agent = token.user_agent,
    )

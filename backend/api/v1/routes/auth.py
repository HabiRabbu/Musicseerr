"""Auth routes: setup, local login/registration, sessions, admin user management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.v1.schemas.auth import (
    AuthResponse,
    LoginRequest,
    CreateUserRequest,
    SessionListResponse,
    SetRoleRequest,
    SetupRequest,
    SetupStatusResponse,
    UserListResponse,
    session_to_response,
    user_to_response,
)
from core.dependencies.auth_providers import get_auth_service
from core.exceptions import AuthenticationError, RegistrationError
from infrastructure.msgspec_fastapi import MsgSpecRoute
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(route_class = MsgSpecRoute, prefix = "/auth", tags = ["auth"])


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _require_token(request: Request) -> str:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated",
            headers = {"WWW-Authenticate": "Bearer"},
        )
    return token


async def _require_admin(request: Request, auth: AuthService) -> None:
    raw_token = _require_token(request)
    result = await auth.verify_token(raw_token)
    if result is None:
        raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not authenticated")
    user, _ = result
    if user.role != "admin":
        raise HTTPException(status_code = status.HTTP_403_FORBIDDEN, detail = "Admin access required")


@router.get("/setup/status", response_model = SetupStatusResponse)
async def setup_status(auth: AuthService = Depends(get_auth_service)) -> SetupStatusResponse:
    required = await auth.is_setup_required()
    return SetupStatusResponse(required = required)


@router.post("/setup", response_model = AuthResponse, status_code = status.HTTP_201_CREATED)
async def setup(
    body: SetupRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    if not await auth.is_setup_required():
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "Setup has already been completed",
        )
    try:
        user, token = await auth.create_first_admin(
            display_name = body.display_name,
            email = body.email,
            password = body.password,
            user_agent = request.headers.get("User-Agent"),
        )
    except RegistrationError as e:
        logger.debug(f"Setup registration error: {e}")
        raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail = "Invalid setup data")

    return AuthResponse(token = token, user = user_to_response(user))


@router.post("/login", response_model = AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user, token = await auth.login_local(
            email = body.email,
            password = body.password,
            user_agent = request.headers.get("User-Agent"),
        )
    except AuthenticationError:
        # Always 401, never reveal which field was wrong
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid email or password",
            headers = {"WWW-Authenticate": "Bearer"},
        )

    return AuthResponse(token = token, user = user_to_response(user))


@router.post("/logout", status_code = status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    token = _bearer_token(request)
    if token:
        await auth.logout(token)


@router.post("/logout-all", status_code = status.HTTP_204_NO_CONTENT)
async def logout_all(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    raw_token = _require_token(request)
    result = await auth.verify_token(raw_token)
    if result is None:
        raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not authenticated")
    user, _ = result
    await auth.logout_all(user.id, except_raw_token = raw_token)


@router.get("/me")
async def me(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    raw_token = _require_token(request)
    result = await auth.verify_token(raw_token)
    if result is None:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid or expired token",
            headers = {"WWW-Authenticate": "Bearer"},
        )
    user, _ = result
    return user_to_response(user)


@router.get("/sessions", response_model = SessionListResponse)
async def list_sessions(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> SessionListResponse:
    raw_token = _require_token(request)
    result = await auth.verify_token(raw_token)
    if result is None:
        raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not authenticated")
    user, _ = result
    tokens = await auth.list_sessions(user.id)
    return SessionListResponse(sessions = [session_to_response(token) for token in tokens])


@router.delete("/sessions/{session_id}", status_code = status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    raw_token = _require_token(request)
    result = await auth.verify_token(raw_token)
    if result is None:
        raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not authenticated")
    user, _ = result
    try:
        await auth.revoke_session(session_id, requesting_user_id = user.id)
    except AuthenticationError as e:
        logger.debug(f"Session revocation denied for user {user.id[:8]}: {e}")
        raise HTTPException(status_code = status.HTTP_403_FORBIDDEN, detail = "Forbidden")


@router.get("/admin/users", response_model = UserListResponse)
async def admin_list_users(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> UserListResponse:
    await _require_admin(request, auth)
    users = await auth.list_users()
    return UserListResponse(
        users = [user_to_response(user) for user in users],
        total = len(users),
    )


@router.post("/admin/users", status_code = status.HTTP_201_CREATED)
async def admin_create_user(
    body: CreateUserRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    await _require_admin(request, auth)
    try:
        user = await auth.admin_create_user(
            display_name = body.display_name,
            email = body.email,
            password = body.password,
            role = body.role,
        )
    except RegistrationError as e:
        logger.debug(f"Admin user creation failed: {e}")
        raise HTTPException(status_code = status.HTTP_409_CONFLICT, detail = "Could not create user")
    return user_to_response(user)


@router.patch("/admin/users/{user_id}/role", status_code = status.HTTP_204_NO_CONTENT)
async def admin_set_role(
    user_id: str,
    body: SetRoleRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    await _require_admin(request, auth)
    try:
        await auth.set_role(user_id, body.role)
    except AuthenticationError as e:
        logger.debug(f"Role update failed for user {user_id[:8]}: {e}")
        raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail = "Invalid role")


@router.delete("/admin/users/{user_id}/sessions", status_code = status.HTTP_204_NO_CONTENT)
async def admin_revoke_user_sessions(
    user_id: str,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    await _require_admin(request, auth)
    await auth.revoke_user_sessions(user_id)

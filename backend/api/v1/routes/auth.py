import logging

from fastapi import APIRouter, Depends, HTTPException

from api.v1.schemas.auth import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthSetupRequest,
    AuthStatusResponse,
    AuthSettingsResponse,
)
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    from core.dependencies import get_auth_service as _get
    return _get()


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(auth: AuthService = Depends(get_auth_service)):
    return AuthStatusResponse(
        auth_enabled=auth.is_auth_enabled(),
        setup_required=auth.setup_required(),
    )


@router.post("/setup", response_model=AuthLoginResponse)
async def setup(
    body: AuthSetupRequest = MsgSpecBody(AuthSetupRequest),
    auth: AuthService = Depends(get_auth_service),
):
    """Create the first admin account. Only works when no users exist yet."""
    if auth.user_count() > 0:
        raise HTTPException(status_code=403, detail="Setup already complete")
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    try:
        auth.create_user(body.username, body.password, role="admin")
        # Auto-enable auth on first setup
        auth.set_auth_enabled(True)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token = auth.create_token(body.username, "admin")
    return AuthLoginResponse(token=token, username=body.username, role="admin")


@router.post("/login", response_model=AuthLoginResponse)
async def login(
    body: AuthLoginRequest = MsgSpecBody(AuthLoginRequest),
    auth: AuthService = Depends(get_auth_service),
):
    user = auth.verify_password(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth.create_token(user["username"], user["role"])
    return AuthLoginResponse(token=token, username=user["username"], role=user["role"])


@router.get("/settings", response_model=AuthSettingsResponse)
async def get_auth_settings(auth: AuthService = Depends(get_auth_service)):
    return AuthSettingsResponse(enabled=auth.is_auth_enabled())


@router.put("/settings", response_model=AuthSettingsResponse)
async def update_auth_settings(
    body: AuthSettingsResponse = MsgSpecBody(AuthSettingsResponse),
    auth: AuthService = Depends(get_auth_service),
):
    if body.enabled and auth.user_count() == 0:
        raise HTTPException(
            status_code=400,
            detail="NO_USERS",
        )
    auth.set_auth_enabled(body.enabled)
    return AuthSettingsResponse(enabled=auth.is_auth_enabled())

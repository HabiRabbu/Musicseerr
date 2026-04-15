import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.v1.schemas.auth import (
    DefaultRequestSettings,
    UpdateUserRequest,
    UserSummary,
)
from core.dependencies import get_auth_service
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/admin", tags=["admin"])


def _require_admin(request: Request) -> dict:
    current_user = getattr(request.state, "current_user", None)
    if current_user is None or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/users", response_model=list[UserSummary])
async def list_users(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    _require_admin(request)
    return [UserSummary(**u) for u in auth.get_all_users()]


@router.put("/users/{username}", response_model=UserSummary)
async def update_user(
    username: str,
    request: Request,
    body: UpdateUserRequest = MsgSpecBody(UpdateUserRequest),
    auth: AuthService = Depends(get_auth_service),
):
    current = _require_admin(request)
    # Prevent demoting yourself
    if username.lower() == current["username"].lower() and body.role and body.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote your own account")
    updated = auth.update_user(
        username,
        role=body.role,
        can_request=body.can_request,
        request_quota=body.request_quota,
        quota_days=body.quota_days,
        clear_quota=body.clear_quota,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    users = auth.get_all_users()
    for u in users:
        if u["username"].lower() == username.lower():
            return UserSummary(**u)
    raise HTTPException(status_code=404, detail="User not found")


@router.delete("/users/{username}", status_code=204)
async def delete_user(
    username: str,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    current = _require_admin(request)
    if username.lower() == current["username"].lower():
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    deleted = auth.delete_user(username)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/settings/requests", response_model=DefaultRequestSettings)
async def get_request_settings(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    _require_admin(request)
    s = auth.get_default_request_settings()
    return DefaultRequestSettings(
        quota=s.get("quota"),
        quota_days=s.get("quota_days", 7),
        can_request=s.get("can_request", True),
    )


@router.put("/settings/requests", response_model=DefaultRequestSettings)
async def update_request_settings(
    request: Request,
    body: DefaultRequestSettings = MsgSpecBody(DefaultRequestSettings),
    auth: AuthService = Depends(get_auth_service),
):
    _require_admin(request)
    auth.set_default_request_settings(
        quota=body.quota,
        quota_days=body.quota_days,
        can_request=body.can_request,
    )
    return body

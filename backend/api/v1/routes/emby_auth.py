import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.v1.schemas.settings import EmbyAuthSettings, EmbyVerifyResponse
from core.dependencies import get_preferences_service
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from repositories.emby_repository import emby_verify_server
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/emby", tags=["emby-auth"])


def _require_admin(request: Request) -> None:
    current_user = getattr(request.state, "current_user", None)
    if current_user is None or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/auth/settings", response_model=EmbyAuthSettings)
async def get_emby_settings(
    request: Request,
    preferences: PreferencesService = Depends(get_preferences_service),
):
    _require_admin(request)
    return preferences.get_emby_auth_settings()


@router.put("/auth/settings", response_model=EmbyAuthSettings)
async def save_emby_settings(
    request: Request,
    body: EmbyAuthSettings = MsgSpecBody(EmbyAuthSettings),
    preferences: PreferencesService = Depends(get_preferences_service),
):
    _require_admin(request)
    preferences.save_emby_auth_settings(body)
    return preferences.get_emby_auth_settings()


@router.post("/auth/verify", response_model=EmbyVerifyResponse)
async def verify_emby_server(
    request: Request,
    body: EmbyAuthSettings = MsgSpecBody(EmbyAuthSettings),
):
    _require_admin(request)
    if not body.emby_url:
        return EmbyVerifyResponse(success=False, message="No server URL provided")
    ok, message = await emby_verify_server(body.emby_url)
    return EmbyVerifyResponse(success=ok, message=message)

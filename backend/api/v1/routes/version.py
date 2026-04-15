from fastapi import APIRouter, Depends

from api.v1.schemas.version import GitHubRelease, UpdateCheckResponse, VersionInfo
from core.dependencies import get_version_service
from infrastructure.msgspec_fastapi import MsgSpecRoute
from services.version_service import VersionService

router = APIRouter(route_class=MsgSpecRoute, prefix="/version", tags=["version"])


@router.get("", response_model=VersionInfo)
async def get_version(
    version_service: VersionService = Depends(get_version_service),
):
    return version_service.get_current_version()


@router.get("/check-update", response_model=UpdateCheckResponse)
async def check_update(
    version_service: VersionService = Depends(get_version_service),
):
    return await version_service.check_for_updates()


@router.get("/releases", response_model=list[GitHubRelease])
async def get_releases(
    version_service: VersionService = Depends(get_version_service),
):
    return await version_service.get_release_history()

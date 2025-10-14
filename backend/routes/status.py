from fastapi import APIRouter, HTTPException
from utils.common import ApiError
from utils import lidarr, musicbrainz
from models import StatusReport, ServiceStatus

router = APIRouter(prefix="/api/status")


@router.get("", response_model=StatusReport)
async def get_system_status():
    musicseerr_status = ServiceStatus(status="ok")

    lidarr_status = await lidarr.get_status()

    services = {"musicseerr": musicseerr_status, "lidarr": lidarr_status}

    if lidarr_status.status == "error":
        overall_status = "error"
    elif lidarr_status.status == "ok":
        overall_status = "ok"
    else:
        overall_status = "degraded"

    return StatusReport(status=overall_status, services=services)

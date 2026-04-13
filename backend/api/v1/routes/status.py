from fastapi import APIRouter, Depends
from api.v1.schemas.common import StatusReport
from core.dependencies import get_status_service
from infrastructure.msgspec_fastapi import MsgSpecRoute
from services.status_service import StatusService

router = APIRouter(route_class=MsgSpecRoute, prefix="/status", tags=["status"])


@router.get("", response_model=StatusReport)
async def get_status(
    status_service: StatusService = Depends(get_status_service)
):
    return await status_service.get_status()

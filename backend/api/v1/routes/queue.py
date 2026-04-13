from fastapi import APIRouter, Depends, HTTPException
from api.v1.schemas.request import QueueItem
from core.dependencies import get_lidarr_repository
from infrastructure.msgspec_fastapi import MsgSpecRoute
from repositories.lidarr import LidarrRepository

router = APIRouter(route_class=MsgSpecRoute, prefix="/queue", tags=["queue"])


@router.get("", response_model=list[QueueItem])
async def get_queue(
    lidarr_repo: LidarrRepository = Depends(get_lidarr_repository)
):
    return await lidarr_repo.get_queue()

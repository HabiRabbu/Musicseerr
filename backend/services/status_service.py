import logging
from repositories.lidarr_repository import LidarrRepository
from api.v1.schemas.common import StatusReport, ServiceStatus

logger = logging.getLogger(__name__)


class StatusService:
    def __init__(self, lidarr_repo: LidarrRepository):
        self._lidarr_repo = lidarr_repo
    
    async def get_status(self) -> StatusReport:
        lidarr_status = await self._lidarr_repo.get_status()
        
        services = {
            "lidarr": lidarr_status
        }
        
        overall_status = "ok"
        if any(s.status == "error" for s in services.values()):
            overall_status = "error"
        elif any(s.status != "ok" for s in services.values()):
            overall_status = "degraded"
        
        return StatusReport(
            status=overall_status,
            services=services
        )

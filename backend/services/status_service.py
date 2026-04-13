from repositories.protocols import LidarrRepositoryProtocol
from api.v1.schemas.common import StatusReport, ServiceStatus


class StatusService:
    def __init__(self, lidarr_repo: LidarrRepositoryProtocol):
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

import logging
from repositories.lidarr_repository import LidarrRepository
from infrastructure.queue.request_queue import RequestQueue
from api.v1.schemas.request import QueueStatusResponse
from core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class RequestService:
    def __init__(
        self,
        lidarr_repo: LidarrRepository,
        request_queue: RequestQueue
    ):
        self._lidarr_repo = lidarr_repo
        self._request_queue = request_queue
    
    async def request_album(self, musicbrainz_id: str) -> dict:
        try:
            result = await self._request_queue.add(musicbrainz_id)
            return {
                "success": True,
                "message": result["message"],
                "lidarr_response": result["payload"]
            }
        except Exception as e:
            logger.error(f"Failed to request album {musicbrainz_id}: {e}")
            raise ExternalServiceError(f"Failed to request album: {e}")
    
    def get_queue_status(self) -> QueueStatusResponse:
        status = self._request_queue.get_status()
        return QueueStatusResponse(
            queue_size=status["queue_size"],
            processing=status["processing"]
        )

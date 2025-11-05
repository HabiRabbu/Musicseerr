import logging
from typing import Any
from repositories.lidarr_repository import LidarrRepository
from api.v1.schemas.library import LibraryAlbum
from core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(self, lidarr_repo: LidarrRepository):
        self._lidarr_repo = lidarr_repo
    
    async def get_library(self) -> list[LibraryAlbum]:
        try:
            return await self._lidarr_repo.get_library()
        except Exception as e:
            logger.error(f"Failed to fetch library: {e}")
            raise ExternalServiceError(f"Failed to fetch library: {e}")
    
    async def get_library_grouped(self) -> list[dict[str, Any]]:
        try:
            return await self._lidarr_repo.get_library_grouped()
        except Exception as e:
            logger.error(f"Failed to fetch grouped library: {e}")
            raise ExternalServiceError(f"Failed to fetch grouped library: {e}")

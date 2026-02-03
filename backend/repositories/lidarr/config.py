import logging
from typing import Any
from api.v1.schemas.common import ServiceStatus
from api.v1.schemas.request import QueueItem
from .base import LidarrBase

logger = logging.getLogger(__name__)


class LidarrConfigRepository(LidarrBase):
    async def get_status(self) -> ServiceStatus:
        try:
            data = await self._get("/api/v1/system/status")
            return ServiceStatus(status="ok", version=data.get("version"))
        except Exception as e:
            return ServiceStatus(status="error", message=str(e))

    async def get_queue(self) -> list[QueueItem]:
        data = await self._get("/api/v1/queue")
        items = data.get("records", []) if isinstance(data, dict) else data

        queue_items = []
        for item in items:
            album_data = item.get("album", {})
            artist_data = album_data.get("artist", {})

            queue_items.append(
                QueueItem(
                    artist=artist_data.get("artistName", "Unknown"),
                    album=album_data.get("title", "Unknown"),
                    status=item.get("status", "unknown"),
                    progress=None,
                    eta=None,
                    musicbrainz_id=album_data.get("foreignAlbumId"),
                )
            )

        return queue_items

    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/qualityprofile")

    async def get_metadata_profiles(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/metadataprofile")

    async def get_root_folders(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/rootfolder")

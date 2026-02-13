import logging
from typing import Any, Optional
from .base import LidarrBase

logger = logging.getLogger(__name__)


class LidarrQueueRepository(LidarrBase):
    async def get_queue_details(
        self,
        include_artist: bool = True,
        include_album: bool = True,
    ) -> list[dict[str, Any]]:
        params = {
            "page": 1,
            "pageSize": 100,
            "includeArtist": str(include_artist).lower(),
            "includeAlbum": str(include_album).lower(),
        }
        data = await self._get("/api/v1/queue", params=params)
        if isinstance(data, dict):
            return data.get("records", [])
        return data if isinstance(data, list) else []

    async def remove_queue_item(
        self,
        queue_id: int,
        remove_from_client: bool = True,
    ) -> bool:
        params = {
            "removeFromClient": str(remove_from_client).lower(),
            "blocklist": "false",
            "skipRedownload": "false",
            "changeCategory": "false",
        }
        try:
            await self._delete(f"/api/v1/queue/{queue_id}", params=params)
            return True
        except Exception as e:
            logger.error("Failed to remove queue item %s: %s", queue_id, e)
            return False

    async def get_history_for_album(
        self,
        album_id: int,
        include_album: bool = True,
        include_artist: bool = True,
    ) -> list[dict[str, Any]]:
        params = {
            "albumId": album_id,
            "includeAlbum": str(include_album).lower(),
            "includeArtist": str(include_artist).lower(),
        }
        data = await self._get("/api/v1/history", params=params)
        if isinstance(data, dict):
            return data.get("records", [])
        return data if isinstance(data, list) else []

    async def trigger_album_search(self, album_ids: list[int]) -> Optional[dict[str, Any]]:
        try:
            return await self._post("/api/v1/command", {
                "name": "AlbumSearch",
                "albumIds": album_ids,
            })
        except Exception as e:
            logger.error("Failed to trigger album search: %s", e)
            return None

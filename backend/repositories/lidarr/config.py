from typing import Any
from models.common import ServiceStatus
from models.request import QueueItem
from infrastructure.cache.cache_keys import LIDARR_PREFIX
from .base import LidarrBase

LIDARR_QUEUE_KEY = f"{LIDARR_PREFIX}queue"
LIDARR_QUEUE_TTL = 30


class LidarrConfigRepository(LidarrBase):
    async def get_status(self) -> ServiceStatus:
        try:
            data = await self._get("/api/v1/system/status")
            return ServiceStatus(status="ok", version=data.get("version"))
        except Exception as e:  # noqa: BLE001
            return ServiceStatus(status="error", message=str(e))

    async def get_queue(self) -> list[QueueItem]:
        cached = await self._cache.get(LIDARR_QUEUE_KEY)
        if cached is not None:
            return cached

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

        await self._cache.set(LIDARR_QUEUE_KEY, queue_items, ttl_seconds=LIDARR_QUEUE_TTL)
        return queue_items

    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/qualityprofile")

    async def get_metadata_profiles(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/metadataprofile")

    async def get_metadata_profile(self, profile_id: int) -> dict[str, Any]:
        return await self._get(f"/api/v1/metadataprofile/{profile_id}")

    async def update_metadata_profile(
        self, profile_id: int, profile_data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._put(f"/api/v1/metadataprofile/{profile_id}", profile_data)

    async def get_root_folders(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/rootfolder")

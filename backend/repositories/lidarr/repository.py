import httpx
from typing import Any, Optional
from core.config import Settings
from api.v1.schemas.library import LibraryAlbum
from api.v1.schemas.request import QueueItem
from api.v1.schemas.common import ServiceStatus
from infrastructure.cache.memory_cache import CacheInterface
from .library import LidarrLibraryRepository
from .artist import LidarrArtistRepository
from .album import LidarrAlbumRepository
from .config import LidarrConfigRepository
from .queue import LidarrQueueRepository


class LidarrRepository(
    LidarrLibraryRepository,
    LidarrArtistRepository,
    LidarrAlbumRepository,
    LidarrConfigRepository,
    LidarrQueueRepository
):
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        cache: CacheInterface
    ):
        super().__init__(settings, http_client, cache)

    async def add_album(self, musicbrainz_id: str) -> dict:
        return await LidarrAlbumRepository.add_album(self, musicbrainz_id, self)

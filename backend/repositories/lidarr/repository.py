import httpx
from typing import Any, Optional, TYPE_CHECKING
from core.config import Settings
from models.library import LibraryAlbum
from models.request import QueueItem
from models.common import ServiceStatus
from infrastructure.cache.memory_cache import CacheInterface
from .library import LidarrLibraryRepository
from .artist import LidarrArtistRepository
from .album import LidarrAlbumRepository
from .config import LidarrConfigRepository
from .queue import LidarrQueueRepository

if TYPE_CHECKING:
    from infrastructure.persistence.request_history import RequestHistoryStore


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
        cache: CacheInterface,
        request_history_store: "RequestHistoryStore | None" = None,
    ):
        super().__init__(settings, http_client, cache)
        self._request_history_store = request_history_store

    async def add_album(self, musicbrainz_id: str) -> dict:
        return await LidarrAlbumRepository.add_album(self, musicbrainz_id, self)

from core.config import get_settings
from infrastructure.cache.memory_cache import InMemoryCache, CacheInterface
from infrastructure.http.client import get_http_client, close_http_clients
from infrastructure.queue.request_queue import RequestQueue
from repositories.lidarr_repository import LidarrRepository
from repositories.musicbrainz_repository import MusicBrainzRepository
from repositories.wikidata_repository import WikidataRepository
from repositories.coverart_repository import CoverArtRepository
from services.preferences_service import PreferencesService
from services.search_service import SearchService
from services.artist_service import ArtistService
from services.album_service import AlbumService
from services.request_service import RequestService
from services.library_service import LibraryService
from services.status_service import StatusService
from services.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)


_cache_instance: CacheInterface | None = None
_request_queue_instance: RequestQueue | None = None


def get_cache() -> CacheInterface:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = InMemoryCache()
    return _cache_instance


def get_coverart_repository() -> CoverArtRepository:
    settings = get_settings()
    cache = get_cache()
    mb_repo = get_musicbrainz_repository()
    http_client = get_http_client(settings)
    return CoverArtRepository(http_client, cache, mb_repo)


def get_lidarr_repository() -> LidarrRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    return LidarrRepository(settings, http_client, cache)


def get_musicbrainz_repository() -> MusicBrainzRepository:
    cache = get_cache()
    return MusicBrainzRepository(cache)


def get_wikidata_repository() -> WikidataRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    return WikidataRepository(http_client, cache)


def get_preferences_service() -> PreferencesService:
    settings = get_settings()
    return PreferencesService(settings)


def get_search_service() -> SearchService:
    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    coverart_repo = get_coverart_repository()
    preferences_service = get_preferences_service()
    return SearchService(mb_repo, lidarr_repo, coverart_repo, preferences_service)


def get_artist_service() -> ArtistService:
    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    wikidata_repo = get_wikidata_repository()
    preferences_service = get_preferences_service()
    return ArtistService(mb_repo, lidarr_repo, wikidata_repo, preferences_service)


def get_album_service() -> AlbumService:
    lidarr_repo = get_lidarr_repository()
    mb_repo = get_musicbrainz_repository()
    return AlbumService(lidarr_repo, mb_repo)


def get_request_queue() -> RequestQueue:
    global _request_queue_instance
    if _request_queue_instance is None:
        lidarr_repo = get_lidarr_repository()
        
        async def processor(album_mbid: str) -> dict:
            return await lidarr_repo.add_album(album_mbid)
        
        _request_queue_instance = RequestQueue(processor)
    return _request_queue_instance


def get_request_service() -> RequestService:
    lidarr_repo = get_lidarr_repository()
    request_queue = get_request_queue()
    return RequestService(lidarr_repo, request_queue)


def get_library_service() -> LibraryService:
    lidarr_repo = get_lidarr_repository()
    return LibraryService(lidarr_repo)


def get_status_service() -> StatusService:
    lidarr_repo = get_lidarr_repository()
    return StatusService(lidarr_repo)


def get_cache_service() -> CacheService:
    cache = get_cache()
    return CacheService(cache)


async def init_app_state(app) -> None:
    """Initialize application state during startup."""
    # Cache and queue are already initialized via their getters
    # This is a placeholder for future initialization needs
    logger.info("Application state initialized")


async def cleanup_app_state() -> None:
    """Cleanup application state during shutdown."""
    # Close HTTP clients
    await close_http_clients()
    logger.info("Application state cleaned up")

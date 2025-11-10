from core.config import get_settings
from infrastructure.cache.memory_cache import InMemoryCache, CacheInterface
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cache.disk_cache import DiskMetadataCache
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
_library_cache_instance: LibraryCache | None = None
_disk_cache_instance: DiskMetadataCache | None = None
_request_queue_instance: RequestQueue | None = None


def get_cache() -> CacheInterface:
    global _cache_instance
    if _cache_instance is None:
        settings = get_settings()
        max_entries = settings.metadata_cache_max_entries
        _cache_instance = InMemoryCache(max_entries=max_entries)
        logger.info(f"Initialized RAM cache with max {max_entries} entries (hot items only)")
    return _cache_instance


def get_disk_cache() -> DiskMetadataCache:
    global _disk_cache_instance
    if _disk_cache_instance is None:
        settings = get_settings()
        cache_dir = settings.cache_dir / "metadata"
        _disk_cache_instance = DiskMetadataCache(base_path=cache_dir)
        logger.info(f"Initialized disk metadata cache at {cache_dir}")
    return _disk_cache_instance


def get_library_cache() -> LibraryCache:
    global _library_cache_instance
    if _library_cache_instance is None:
        settings = get_settings()
        _library_cache_instance = LibraryCache(db_path=settings.library_db_path)
        logger.info(f"Initialized library cache at {settings.library_db_path}")
    return _library_cache_instance


def get_coverart_repository() -> CoverArtRepository:
    settings = get_settings()
    cache = get_cache()
    mb_repo = get_musicbrainz_repository()
    http_client = get_http_client(settings)
    cache_dir = settings.cache_dir / "covers"
    return CoverArtRepository(http_client, cache, mb_repo, cache_dir=cache_dir)


def get_lidarr_repository() -> LidarrRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    return LidarrRepository(settings, http_client, cache)


def get_musicbrainz_repository() -> MusicBrainzRepository:
    cache = get_cache()
    preferences_service = get_preferences_service()
    return MusicBrainzRepository(cache, preferences_service)


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
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    return ArtistService(mb_repo, lidarr_repo, wikidata_repo, preferences_service, memory_cache, disk_cache)


def get_album_service() -> AlbumService:
    lidarr_repo = get_lidarr_repository()
    mb_repo = get_musicbrainz_repository()
    library_cache = get_library_cache()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    preferences_service = get_preferences_service()
    return AlbumService(lidarr_repo, mb_repo, library_cache, memory_cache, disk_cache, preferences_service)


def get_request_queue() -> RequestQueue:
    global _request_queue_instance
    if _request_queue_instance is None:
        lidarr_repo = get_lidarr_repository()
        disk_cache = get_disk_cache()
        cover_repo = get_coverart_repository()
        
        async def processor(album_mbid: str) -> dict:
            result = await lidarr_repo.add_album(album_mbid)
            
            payload = result.get("payload", {})
            if payload and isinstance(payload, dict):
                is_monitored = payload.get("monitored", False)
                
                if is_monitored:
                    logger.info(f"Album {album_mbid[:8]}... successfully monitored - promoting cache entries to persistent")
                    
                    try:
                        await disk_cache.promote_album_to_persistent(album_mbid)
                        await cover_repo.promote_cover_to_persistent(album_mbid, identifier_type="album")
                        
                        artist_data = payload.get("artist", {})
                        if artist_data:
                            artist_mbid = artist_data.get("foreignArtistId") or artist_data.get("mbId")
                            if artist_mbid:
                                await disk_cache.promote_artist_to_persistent(artist_mbid)
                                await cover_repo.promote_cover_to_persistent(artist_mbid, identifier_type="artist")
                        
                        logger.info(f"Cache promotion complete for album {album_mbid[:8]}...")
                    except Exception as e:
                        logger.error(f"Failed to promote cache entries for album {album_mbid[:8]}...: {e}")
                else:
                    logger.warning(f"Album {album_mbid[:8]}... added but not monitored - skipping cache promotion")
            
            return result
        
        _request_queue_instance = RequestQueue(processor)
    return _request_queue_instance


def get_request_service() -> RequestService:
    lidarr_repo = get_lidarr_repository()
    request_queue = get_request_queue()
    return RequestService(lidarr_repo, request_queue)


def get_library_service() -> LibraryService:
    lidarr_repo = get_lidarr_repository()
    library_cache = get_library_cache()
    cover_repo = get_coverart_repository()
    preferences_service = get_preferences_service()
    return LibraryService(lidarr_repo, library_cache, cover_repo, preferences_service)


def get_status_service() -> StatusService:
    lidarr_repo = get_lidarr_repository()
    return StatusService(lidarr_repo)


def get_cache_service() -> CacheService:
    cache = get_cache()
    library_cache = get_library_cache()
    disk_cache = get_disk_cache()
    return CacheService(cache, library_cache, disk_cache)


async def init_app_state(app) -> None:
    logger.info("Application state initialized")


async def cleanup_app_state() -> None:
    await close_http_clients()
    logger.info("Application state cleaned up")

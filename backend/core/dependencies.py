from functools import lru_cache
import logging
from typing import Annotated

from fastapi import Depends

from core.config import Settings, get_settings
from infrastructure.cache.memory_cache import InMemoryCache, CacheInterface
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.http.client import get_http_client, close_http_clients
from infrastructure.queue.request_queue import RequestQueue
from repositories.lidarr import LidarrRepository
from repositories.musicbrainz_repository import MusicBrainzRepository
from repositories.wikidata_repository import WikidataRepository
from repositories.coverart_repository import CoverArtRepository
from repositories.listenbrainz_repository import ListenBrainzRepository
from repositories.jellyfin_repository import JellyfinRepository
from repositories.youtube import YouTubeRepository
from services.preferences_service import PreferencesService
from services.search_service import SearchService
from services.search_enrichment_service import SearchEnrichmentService
from services.artist_service import ArtistService
from services.album_service import AlbumService
from services.request_service import RequestService
from services.library_service import LibraryService
from services.status_service import StatusService
from services.cache_service import CacheService
from services.home_service import HomeService
from services.home_charts_service import HomeChartsService
from services.settings_service import SettingsService
from services.artist_discovery_service import ArtistDiscoveryService
from services.album_discovery_service import AlbumDiscoveryService
from services.discover_service import DiscoverService

logger = logging.getLogger(__name__)

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache(maxsize=1)
def get_cache() -> CacheInterface:
    settings = get_settings()
    max_entries = settings.metadata_cache_max_entries
    logger.info(f"Initialized RAM cache with max {max_entries} entries")
    return InMemoryCache(max_entries=max_entries)


@lru_cache(maxsize=1)
def get_disk_cache() -> DiskMetadataCache:
    settings = get_settings()
    cache_dir = settings.cache_dir / "metadata"
    logger.info(f"Initialized disk metadata cache at {cache_dir}")
    return DiskMetadataCache(base_path=cache_dir)


@lru_cache(maxsize=1)
def get_library_cache() -> LibraryCache:
    settings = get_settings()
    logger.info(f"Initialized library cache at {settings.library_db_path}")
    return LibraryCache(db_path=settings.library_db_path)


@lru_cache(maxsize=1)
def get_preferences_service() -> PreferencesService:
    settings = get_settings()
    return PreferencesService(settings)


@lru_cache(maxsize=1)
def get_lidarr_repository() -> LidarrRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    return LidarrRepository(settings, http_client, cache)


@lru_cache(maxsize=1)
def get_musicbrainz_repository() -> MusicBrainzRepository:
    cache = get_cache()
    preferences_service = get_preferences_service()
    return MusicBrainzRepository(cache, preferences_service)


@lru_cache(maxsize=1)
def get_wikidata_repository() -> WikidataRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    return WikidataRepository(http_client, cache)


@lru_cache(maxsize=1)
def get_listenbrainz_repository() -> ListenBrainzRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    preferences = get_preferences_service()
    lb_settings = preferences.get_listenbrainz_connection()
    return ListenBrainzRepository(
        http_client=http_client,
        cache=cache,
        username=lb_settings.username if lb_settings.enabled else "",
        user_token=lb_settings.user_token if lb_settings.enabled else "",
    )


@lru_cache(maxsize=1)
def get_jellyfin_repository() -> JellyfinRepository:
    settings = get_settings()
    cache = get_cache()
    http_client = get_http_client(settings)
    preferences = get_preferences_service()
    jf_settings = preferences.get_jellyfin_connection()
    return JellyfinRepository(
        http_client=http_client,
        cache=cache,
        base_url=jf_settings.jellyfin_url if jf_settings.enabled else "",
        api_key=jf_settings.api_key if jf_settings.enabled else "",
        user_id=jf_settings.user_id if jf_settings.enabled else "",
    )


@lru_cache(maxsize=1)
def get_coverart_repository() -> CoverArtRepository:
    settings = get_settings()
    cache = get_cache()
    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    http_client = get_http_client(settings)
    cache_dir = settings.cache_dir / "covers"
    return CoverArtRepository(http_client, cache, mb_repo, lidarr_repo, cache_dir=cache_dir)


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    coverart_repo = get_coverart_repository()
    preferences_service = get_preferences_service()
    return SearchService(mb_repo, lidarr_repo, coverart_repo, preferences_service)


@lru_cache(maxsize=1)
def get_artist_service() -> ArtistService:
    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    wikidata_repo = get_wikidata_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    return ArtistService(mb_repo, lidarr_repo, wikidata_repo, preferences_service, memory_cache, disk_cache)


@lru_cache(maxsize=1)
def get_album_service() -> AlbumService:
    lidarr_repo = get_lidarr_repository()
    mb_repo = get_musicbrainz_repository()
    library_cache = get_library_cache()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    preferences_service = get_preferences_service()
    return AlbumService(lidarr_repo, mb_repo, library_cache, memory_cache, disk_cache, preferences_service)


@lru_cache(maxsize=1)
def get_request_queue() -> RequestQueue:
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

    return RequestQueue(processor)


@lru_cache(maxsize=1)
def get_request_service() -> RequestService:
    lidarr_repo = get_lidarr_repository()
    request_queue = get_request_queue()
    return RequestService(lidarr_repo, request_queue)


@lru_cache(maxsize=1)
def get_library_service() -> LibraryService:
    lidarr_repo = get_lidarr_repository()
    library_cache = get_library_cache()
    cover_repo = get_coverart_repository()
    preferences_service = get_preferences_service()
    return LibraryService(lidarr_repo, library_cache, cover_repo, preferences_service)


@lru_cache(maxsize=1)
def get_status_service() -> StatusService:
    lidarr_repo = get_lidarr_repository()
    return StatusService(lidarr_repo)


@lru_cache(maxsize=1)
def get_cache_service() -> CacheService:
    cache = get_cache()
    library_cache = get_library_cache()
    disk_cache = get_disk_cache()
    return CacheService(cache, library_cache, disk_cache)


@lru_cache(maxsize=1)
def get_home_service() -> HomeService:
    listenbrainz_repo = get_listenbrainz_repository()
    jellyfin_repo = get_jellyfin_repository()
    lidarr_repo = get_lidarr_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    return HomeService(
        listenbrainz_repo=listenbrainz_repo,
        jellyfin_repo=jellyfin_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=musicbrainz_repo,
        preferences_service=preferences_service,
        memory_cache=memory_cache,
    )


@lru_cache(maxsize=1)
def get_home_charts_service() -> HomeChartsService:
    listenbrainz_repo = get_listenbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    library_cache = get_library_cache()
    return HomeChartsService(
        listenbrainz_repo=listenbrainz_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=musicbrainz_repo,
        library_cache=library_cache,
    )


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    preferences_service = get_preferences_service()
    cache = get_cache()
    return SettingsService(preferences_service, cache)


@lru_cache(maxsize=1)
def get_artist_discovery_service() -> ArtistDiscoveryService:
    listenbrainz_repo = get_listenbrainz_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    library_cache = get_library_cache()
    lidarr_repo = get_lidarr_repository()
    return ArtistDiscoveryService(
        listenbrainz_repo=listenbrainz_repo,
        musicbrainz_repo=musicbrainz_repo,
        library_cache=library_cache,
        lidarr_repo=lidarr_repo,
    )


@lru_cache(maxsize=1)
def get_album_discovery_service() -> AlbumDiscoveryService:
    listenbrainz_repo = get_listenbrainz_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    library_cache = get_library_cache()
    lidarr_repo = get_lidarr_repository()
    return AlbumDiscoveryService(
        listenbrainz_repo=listenbrainz_repo,
        musicbrainz_repo=musicbrainz_repo,
        library_cache=library_cache,
        lidarr_repo=lidarr_repo,
    )


@lru_cache(maxsize=1)
def get_search_enrichment_service() -> SearchEnrichmentService:
    mb_repo = get_musicbrainz_repository()
    lb_repo = get_listenbrainz_repository()
    preferences_service = get_preferences_service()
    return SearchEnrichmentService(mb_repo, lb_repo, preferences_service)


@lru_cache(maxsize=1)
def get_youtube_repo() -> YouTubeRepository:
    settings = get_settings()
    http_client = get_http_client(settings)
    preferences_service = get_preferences_service()
    yt_settings = preferences_service.get_youtube_connection()
    api_key = yt_settings.api_key if yt_settings.enabled else ""
    return YouTubeRepository(http_client=http_client, api_key=api_key)


@lru_cache(maxsize=1)
def get_discover_service() -> DiscoverService:
    listenbrainz_repo = get_listenbrainz_repository()
    jellyfin_repo = get_jellyfin_repository()
    lidarr_repo = get_lidarr_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    library_cache = get_library_cache()
    wikidata_repo = get_wikidata_repository()
    return DiscoverService(
        listenbrainz_repo=listenbrainz_repo,
        jellyfin_repo=jellyfin_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=musicbrainz_repo,
        preferences_service=preferences_service,
        memory_cache=memory_cache,
        library_cache=library_cache,
        wikidata_repo=wikidata_repo,
    )


CacheDep = Annotated[CacheInterface, Depends(get_cache)]
DiskCacheDep = Annotated[DiskMetadataCache, Depends(get_disk_cache)]
LibraryCacheDep = Annotated[LibraryCache, Depends(get_library_cache)]
PreferencesServiceDep = Annotated[PreferencesService, Depends(get_preferences_service)]
LidarrRepositoryDep = Annotated[LidarrRepository, Depends(get_lidarr_repository)]
MusicBrainzRepositoryDep = Annotated[MusicBrainzRepository, Depends(get_musicbrainz_repository)]
WikidataRepositoryDep = Annotated[WikidataRepository, Depends(get_wikidata_repository)]
ListenBrainzRepositoryDep = Annotated[ListenBrainzRepository, Depends(get_listenbrainz_repository)]
JellyfinRepositoryDep = Annotated[JellyfinRepository, Depends(get_jellyfin_repository)]
CoverArtRepositoryDep = Annotated[CoverArtRepository, Depends(get_coverart_repository)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
SearchEnrichmentServiceDep = Annotated[SearchEnrichmentService, Depends(get_search_enrichment_service)]
ArtistServiceDep = Annotated[ArtistService, Depends(get_artist_service)]
AlbumServiceDep = Annotated[AlbumService, Depends(get_album_service)]
RequestQueueDep = Annotated[RequestQueue, Depends(get_request_queue)]
RequestServiceDep = Annotated[RequestService, Depends(get_request_service)]
LibraryServiceDep = Annotated[LibraryService, Depends(get_library_service)]
StatusServiceDep = Annotated[StatusService, Depends(get_status_service)]
CacheServiceDep = Annotated[CacheService, Depends(get_cache_service)]
HomeServiceDep = Annotated[HomeService, Depends(get_home_service)]
HomeChartsServiceDep = Annotated[HomeChartsService, Depends(get_home_charts_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
ArtistDiscoveryServiceDep = Annotated[ArtistDiscoveryService, Depends(get_artist_discovery_service)]
AlbumDiscoveryServiceDep = Annotated[AlbumDiscoveryService, Depends(get_album_discovery_service)]
DiscoverServiceDep = Annotated[DiscoverService, Depends(get_discover_service)]
YouTubeRepositoryDep = Annotated[YouTubeRepository, Depends(get_youtube_repo)]


async def init_app_state(app) -> None:
    logger.info("Application state initialized")


async def cleanup_app_state() -> None:
    await close_http_clients()

    get_cache.cache_clear()
    get_disk_cache.cache_clear()
    get_library_cache.cache_clear()
    get_preferences_service.cache_clear()
    get_lidarr_repository.cache_clear()
    get_musicbrainz_repository.cache_clear()
    get_wikidata_repository.cache_clear()
    get_listenbrainz_repository.cache_clear()
    get_jellyfin_repository.cache_clear()
    get_coverart_repository.cache_clear()
    get_search_service.cache_clear()
    get_search_enrichment_service.cache_clear()
    get_artist_service.cache_clear()
    get_album_service.cache_clear()
    get_request_queue.cache_clear()
    get_request_service.cache_clear()
    get_library_service.cache_clear()
    get_status_service.cache_clear()
    get_cache_service.cache_clear()
    get_home_service.cache_clear()
    get_home_charts_service.cache_clear()
    get_settings_service.cache_clear()
    get_artist_discovery_service.cache_clear()
    get_album_discovery_service.cache_clear()
    get_youtube_repo.cache_clear()
    get_discover_service.cache_clear()

    logger.info("Application state cleaned up")

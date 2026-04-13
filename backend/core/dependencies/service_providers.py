"""Tier 4 - Business-logic service providers."""

from __future__ import annotations

import asyncio
import logging

from infrastructure.cache.cache_keys import (
    lidarr_raw_albums_key,
    lidarr_requested_mbids_key,
    HOME_RESPONSE_PREFIX,
    ALBUM_INFO_PREFIX,
    ARTIST_INFO_PREFIX,
    LIDARR_PREFIX,
    LIDARR_ALBUM_DETAILS_PREFIX,
)
from infrastructure.persistence.request_history import RequestHistoryRecord

from ._registry import singleton
from .cache_providers import (
    get_cache,
    get_disk_cache,
    get_library_db,
    get_genre_index,
    get_youtube_store,
    get_mbid_store,
    get_sync_state_store,
    get_preferences_service,
    get_cache_status_service,
)
from .repo_providers import (
    get_lidarr_repository,
    get_musicbrainz_repository,
    get_wikidata_repository,
    get_listenbrainz_repository,
    get_jellyfin_repository,
    get_navidrome_repository,
    get_plex_repository,
    get_coverart_repository,
    get_youtube_repo,
    get_audiodb_image_service,
    get_audiodb_browse_queue,
    get_lastfm_repository,
    get_playlist_repository,
    get_request_history_store,
)

logger = logging.getLogger(__name__)


@singleton
def get_search_service() -> "SearchService":
    from services.search_service import SearchService

    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    coverart_repo = get_coverart_repository()
    preferences_service = get_preferences_service()
    audiodb_image_service = get_audiodb_image_service()
    browse_queue = get_audiodb_browse_queue()
    return SearchService(mb_repo, lidarr_repo, coverart_repo, preferences_service, audiodb_image_service, browse_queue)


@singleton
def get_artist_service() -> "ArtistService":
    from services.artist_service import ArtistService

    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    wikidata_repo = get_wikidata_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    audiodb_image_service = get_audiodb_image_service()
    browse_queue = get_audiodb_browse_queue()
    library_db = get_library_db()
    return ArtistService(mb_repo, lidarr_repo, wikidata_repo, preferences_service, memory_cache, disk_cache, audiodb_image_service, browse_queue, library_db)


@singleton
def get_album_service() -> "AlbumService":
    from services.album_service import AlbumService

    lidarr_repo = get_lidarr_repository()
    mb_repo = get_musicbrainz_repository()
    library_db = get_library_db()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    preferences_service = get_preferences_service()
    audiodb_image_service = get_audiodb_image_service()
    browse_queue = get_audiodb_browse_queue()
    return AlbumService(lidarr_repo, mb_repo, library_db, memory_cache, disk_cache, preferences_service, audiodb_image_service, browse_queue)


def make_on_queue_import(memory_cache, disk_cache, library_db):
    """Create the on_queue_import closure used by the request queue."""

    async def on_queue_import(record: RequestHistoryRecord) -> None:
        """Invalidate caches when the queue worker detects an already-imported album."""
        invalidations = [
            memory_cache.delete(lidarr_raw_albums_key()),
            memory_cache.clear_prefix(f"{LIDARR_PREFIX}library:"),
            memory_cache.delete(lidarr_requested_mbids_key()),
            memory_cache.delete(f"{ALBUM_INFO_PREFIX}{record.musicbrainz_id}"),
            memory_cache.delete(f"{LIDARR_ALBUM_DETAILS_PREFIX}{record.musicbrainz_id}"),
        ]
        if record.artist_mbid:
            invalidations.append(
                memory_cache.delete(f"{ARTIST_INFO_PREFIX}{record.artist_mbid}")
            )
            invalidations.append(
                disk_cache.delete_artist(record.artist_mbid)
            )
        await asyncio.gather(*invalidations, return_exceptions=True)
        try:
            await library_db.upsert_album({
                "mbid": record.musicbrainz_id,
                "artist_mbid": record.artist_mbid or "",
                "artist_name": record.artist_name or "",
                "title": record.album_title or "",
                "year": record.year,
                "cover_url": record.cover_url or "",
                "monitored": True,
            })
        except Exception as ex:  # noqa: BLE001
            logger.warning("Queue import: failed to upsert album %s: %s", record.musicbrainz_id[:8], ex)

    return on_queue_import


def make_processor(lidarr_repo, memory_cache, disk_cache, cover_repo, request_history):
    """Create the processor closure used by the request queue."""

    async def processor(album_mbid: str) -> dict:
        result = await lidarr_repo.add_album(album_mbid)

        payload = result.get("payload", {})
        if payload and isinstance(payload, dict):
            is_monitored = payload.get("monitored", False)

            if not is_monitored:
                is_monitored = bool(result.get("monitored"))

            if is_monitored:
                try:
                    await disk_cache.promote_album_to_persistent(album_mbid)
                    await cover_repo.promote_cover_to_persistent(album_mbid, identifier_type="album")

                    artist_data = payload.get("artist", {})
                    if artist_data:
                        artist_mbid = artist_data.get("foreignArtistId") or artist_data.get("mbId")
                        if artist_mbid:
                            await disk_cache.promote_artist_to_persistent(artist_mbid)
                            await cover_repo.promote_cover_to_persistent(artist_mbid, identifier_type="artist")

                except Exception as e:  # noqa: BLE001
                    logger.error(f"Failed to promote cache entries for album {album_mbid[:8]}...: {e}")
            else:
                logger.warning(f"Album {album_mbid[:8]}... added but not monitored - skipping cache promotion")

        try:
            record = await request_history.async_get_record(album_mbid)
            if record and record.monitor_artist and record.artist_mbid:
                monitor_new = "all" if record.auto_download_artist else "none"
                for attempt in range(2):
                    try:
                        await lidarr_repo.update_artist_monitoring(
                            record.artist_mbid, monitored=True, monitor_new_items=monitor_new,
                        )
                        await memory_cache.delete(f"{ARTIST_INFO_PREFIX}{record.artist_mbid}")
                        await disk_cache.delete_artist(record.artist_mbid)
                        break
                    except Exception:  # noqa: BLE001
                        if attempt == 0:
                            await asyncio.sleep(2)
                        else:
                            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to apply deferred artist monitoring for %s: %s", album_mbid[:8], e)

        return result

    return processor


@singleton
def get_request_queue() -> "RequestQueue":
    from infrastructure.queue.request_queue import RequestQueue
    from infrastructure.queue.queue_store import QueueStore
    from core.config import get_settings
    settings = get_settings()

    lidarr_repo = get_lidarr_repository()
    disk_cache = get_disk_cache()
    cover_repo = get_coverart_repository()
    memory_cache = get_cache()
    library_db = get_library_db()

    on_queue_import = make_on_queue_import(memory_cache, disk_cache, library_db)

    store = QueueStore(db_path=settings.queue_db_path)
    request_history = get_request_history_store()

    processor = make_processor(lidarr_repo, memory_cache, disk_cache, cover_repo, request_history)

    concurrency = 2
    try:
        from services.preferences_service import PreferencesService
        prefs = PreferencesService(settings)
        advanced = prefs.get_advanced_settings()
        concurrency = advanced.request_concurrency
    except Exception:  # noqa: BLE001
        pass

    return RequestQueue(
        processor, store=store, request_history=request_history,
        concurrency=concurrency, on_import_callback=on_queue_import,
    )


@singleton
def get_request_service() -> "RequestService":
    from services.request_service import RequestService

    lidarr_repo = get_lidarr_repository()
    request_queue = get_request_queue()
    request_history = get_request_history_store()
    return RequestService(lidarr_repo, request_queue, request_history)


@singleton
def get_requests_page_service() -> "RequestsPageService":
    from services.requests_page_service import RequestsPageService

    lidarr_repo = get_lidarr_repository()
    request_history = get_request_history_store()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    library_db = get_library_db()

    async def on_import(record: RequestHistoryRecord) -> None:
        invalidations = [
            memory_cache.delete(lidarr_raw_albums_key()),
            memory_cache.clear_prefix(f"{LIDARR_PREFIX}library:"),
            memory_cache.delete(lidarr_requested_mbids_key()),
            memory_cache.clear_prefix(HOME_RESPONSE_PREFIX),
            memory_cache.delete(f"{ALBUM_INFO_PREFIX}{record.musicbrainz_id}"),
            memory_cache.delete(f"{LIDARR_ALBUM_DETAILS_PREFIX}{record.musicbrainz_id}"),
        ]
        if record.artist_mbid:
            invalidations.append(
                memory_cache.delete(f"{ARTIST_INFO_PREFIX}{record.artist_mbid}")
            )
        await asyncio.gather(*invalidations, return_exceptions=True)
        if record.artist_mbid:
            await asyncio.gather(
                disk_cache.delete_album(record.musicbrainz_id),
                disk_cache.delete_artist(record.artist_mbid),
                return_exceptions=True,
            )
        else:
            try:
                await disk_cache.delete_album(record.musicbrainz_id)
            except OSError as exc:
                logger.warning(
                    "Failed to delete disk cache album %s during import invalidation: %s",
                    record.musicbrainz_id,
                    exc,
                )
        try:
            await library_db.upsert_album({
                "mbid": record.musicbrainz_id,
                "artist_mbid": record.artist_mbid or "",
                "artist_name": record.artist_name or "",
                "title": record.album_title or "",
                "year": record.year,
                "cover_url": record.cover_url or "",
                "monitored": True,
            })
        except Exception as ex:  # noqa: BLE001
            logger.warning("Failed to upsert album into library cache: %s", ex)

    request_queue = get_request_queue()
    library_service = get_library_service()

    async def merged_library_mbids() -> set[str]:
        return set(await library_service.get_library_mbids())

    return RequestsPageService(
        lidarr_repo=lidarr_repo,
        request_history=request_history,
        library_mbids_fn=merged_library_mbids,
        on_import_callback=on_import,
        request_queue=request_queue,
    )


@singleton
def get_playlist_service() -> "PlaylistService":
    from services.playlist_service import PlaylistService
    from core.config import get_settings

    settings = get_settings()
    playlist_repo = get_playlist_repository()
    return PlaylistService(
        repo=playlist_repo,
        cache_dir=settings.cache_dir,
        cache=get_cache(),
    )


@singleton
def get_library_service() -> "LibraryService":
    from services.library_service import LibraryService

    lidarr_repo = get_lidarr_repository()
    library_db = get_library_db()
    cover_repo = get_coverart_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    disk_cache = get_disk_cache()
    artist_discovery_service = get_artist_discovery_service()
    audiodb_image_service = get_audiodb_image_service()
    local_files_service = get_local_files_service()
    jellyfin_library_service = get_jellyfin_library_service()
    navidrome_library_service = get_navidrome_library_service()
    sync_state_store = get_sync_state_store()
    genre_index = get_genre_index()
    return LibraryService(
        lidarr_repo, library_db, cover_repo, preferences_service,
        memory_cache, disk_cache,
        artist_discovery_service=artist_discovery_service,
        audiodb_image_service=audiodb_image_service,
        local_files_service=local_files_service,
        jellyfin_library_service=jellyfin_library_service,
        navidrome_library_service=navidrome_library_service,
        sync_state_store=sync_state_store,
        genre_index=genre_index,
    )


@singleton
def get_status_service() -> "StatusService":
    from services.status_service import StatusService

    lidarr_repo = get_lidarr_repository()
    return StatusService(lidarr_repo)


@singleton
def get_home_service() -> "HomeService":
    from services.home_service import HomeService
    from core.config import get_settings

    settings = get_settings()
    listenbrainz_repo = get_listenbrainz_repository()
    jellyfin_repo = get_jellyfin_repository()
    lidarr_repo = get_lidarr_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    lastfm_repo = get_lastfm_repository()
    audiodb_image_service = get_audiodb_image_service()
    return HomeService(
        listenbrainz_repo=listenbrainz_repo,
        jellyfin_repo=jellyfin_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=musicbrainz_repo,
        preferences_service=preferences_service,
        memory_cache=memory_cache,
        lastfm_repo=lastfm_repo,
        audiodb_image_service=audiodb_image_service,
        cache_dir=settings.cache_dir,
    )


@singleton
def get_genre_cover_prewarm_service() -> "GenreCoverPrewarmService":
    from services.genre_cover_prewarm_service import GenreCoverPrewarmService

    cover_repo = get_coverart_repository()
    return GenreCoverPrewarmService(cover_repo=cover_repo)


@singleton
def get_home_charts_service() -> "HomeChartsService":
    from services.home_charts_service import HomeChartsService

    listenbrainz_repo = get_listenbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    genre_index = get_genre_index()
    lastfm_repo = get_lastfm_repository()
    preferences_service = get_preferences_service()
    prewarm_service = get_genre_cover_prewarm_service()
    return HomeChartsService(
        listenbrainz_repo=listenbrainz_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=musicbrainz_repo,
        genre_index=genre_index,
        lastfm_repo=lastfm_repo,
        preferences_service=preferences_service,
        prewarm_service=prewarm_service,
    )


@singleton
def get_settings_service() -> "SettingsService":
    from services.settings_service import SettingsService

    preferences_service = get_preferences_service()
    cache = get_cache()
    return SettingsService(preferences_service, cache)


@singleton
def get_artist_discovery_service() -> "ArtistDiscoveryService":
    from services.artist_discovery_service import ArtistDiscoveryService

    listenbrainz_repo = get_listenbrainz_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    library_db = get_library_db()
    lidarr_repo = get_lidarr_repository()
    lastfm_repo = get_lastfm_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    return ArtistDiscoveryService(
        listenbrainz_repo=listenbrainz_repo,
        musicbrainz_repo=musicbrainz_repo,
        library_db=library_db,
        lidarr_repo=lidarr_repo,
        memory_cache=memory_cache,
        lastfm_repo=lastfm_repo,
        preferences_service=preferences_service,
    )


@singleton
def get_artist_enrichment_service() -> "ArtistEnrichmentService":
    from services.artist_enrichment_service import ArtistEnrichmentService

    lastfm_repo = get_lastfm_repository()
    preferences_service = get_preferences_service()
    return ArtistEnrichmentService(
        lastfm_repo=lastfm_repo,
        preferences_service=preferences_service,
    )


@singleton
def get_album_enrichment_service() -> "AlbumEnrichmentService":
    from services.album_enrichment_service import AlbumEnrichmentService

    lastfm_repo = get_lastfm_repository()
    preferences_service = get_preferences_service()
    return AlbumEnrichmentService(
        lastfm_repo=lastfm_repo,
        preferences_service=preferences_service,
    )


@singleton
def get_album_discovery_service() -> "AlbumDiscoveryService":
    from services.album_discovery_service import AlbumDiscoveryService

    listenbrainz_repo = get_listenbrainz_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    library_db = get_library_db()
    lidarr_repo = get_lidarr_repository()
    return AlbumDiscoveryService(
        listenbrainz_repo=listenbrainz_repo,
        musicbrainz_repo=musicbrainz_repo,
        library_db=library_db,
        lidarr_repo=lidarr_repo,
    )


@singleton
def get_search_enrichment_service() -> "SearchEnrichmentService":
    from services.search_enrichment_service import SearchEnrichmentService

    mb_repo = get_musicbrainz_repository()
    lb_repo = get_listenbrainz_repository()
    preferences_service = get_preferences_service()
    lastfm_repo = get_lastfm_repository()
    return SearchEnrichmentService(mb_repo, lb_repo, preferences_service, lastfm_repo)


@singleton
def get_youtube_service() -> "YouTubeService":
    from services.youtube_service import YouTubeService

    youtube_repo = get_youtube_repo()
    youtube_store = get_youtube_store()
    return YouTubeService(youtube_repo=youtube_repo, youtube_store=youtube_store)


@singleton
def get_lastfm_auth_service() -> "LastFmAuthService":
    from services.lastfm_auth_service import LastFmAuthService

    lastfm_repo = get_lastfm_repository()
    return LastFmAuthService(lastfm_repo=lastfm_repo)


@singleton
def get_scrobble_service() -> "ScrobbleService":
    from services.scrobble_service import ScrobbleService

    lastfm_repo = get_lastfm_repository()
    listenbrainz_repo = get_listenbrainz_repository()
    preferences_service = get_preferences_service()
    return ScrobbleService(lastfm_repo, listenbrainz_repo, preferences_service)


@singleton
def get_discover_service() -> "DiscoverService":
    from services.discover_service import DiscoverService

    listenbrainz_repo = get_listenbrainz_repository()
    jellyfin_repo = get_jellyfin_repository()
    lidarr_repo = get_lidarr_repository()
    musicbrainz_repo = get_musicbrainz_repository()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    library_db = get_library_db()
    mbid_store = get_mbid_store()
    wikidata_repo = get_wikidata_repository()
    lastfm_repo = get_lastfm_repository()
    audiodb_image_service = get_audiodb_image_service()
    return DiscoverService(
        listenbrainz_repo=listenbrainz_repo,
        jellyfin_repo=jellyfin_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=musicbrainz_repo,
        preferences_service=preferences_service,
        memory_cache=memory_cache,
        library_db=library_db,
        mbid_store=mbid_store,
        wikidata_repo=wikidata_repo,
        lastfm_repo=lastfm_repo,
        audiodb_image_service=audiodb_image_service,
    )


@singleton
def get_discover_queue_manager() -> "DiscoverQueueManager":
    from services.discover_queue_manager import DiscoverQueueManager

    discover_service = get_discover_service()
    preferences_service = get_preferences_service()
    cover_repo = get_coverart_repository()
    return DiscoverQueueManager(discover_service, preferences_service, cover_repo=cover_repo)


@singleton
def get_jellyfin_playback_service() -> "JellyfinPlaybackService":
    from services.jellyfin_playback_service import JellyfinPlaybackService

    jellyfin_repo = get_jellyfin_repository()
    cache = get_cache()
    return JellyfinPlaybackService(jellyfin_repo, cache)


@singleton
def get_local_files_service() -> "LocalFilesService":
    from services.local_files_service import LocalFilesService

    lidarr_repo = get_lidarr_repository()
    preferences_service = get_preferences_service()
    cache = get_cache()
    return LocalFilesService(lidarr_repo, preferences_service, cache)


@singleton
def get_jellyfin_library_service() -> "JellyfinLibraryService":
    from services.jellyfin_library_service import JellyfinLibraryService

    jellyfin_repo = get_jellyfin_repository()
    preferences_service = get_preferences_service()
    return JellyfinLibraryService(jellyfin_repo, preferences_service)


@singleton
def get_navidrome_library_service() -> "NavidromeLibraryService":
    from services.navidrome_library_service import NavidromeLibraryService

    navidrome_repo = get_navidrome_repository()
    preferences_service = get_preferences_service()
    library_db = get_library_db()
    mbid_store = get_mbid_store()
    return NavidromeLibraryService(navidrome_repo, preferences_service, library_db, mbid_store)


@singleton
def get_navidrome_playback_service() -> "NavidromePlaybackService":
    from services.navidrome_playback_service import NavidromePlaybackService

    navidrome_repo = get_navidrome_repository()
    cache = get_cache()
    return NavidromePlaybackService(navidrome_repo, cache)


@singleton
def get_plex_library_service() -> "PlexLibraryService":
    from services.plex_library_service import PlexLibraryService

    plex_repo = get_plex_repository()
    preferences_service = get_preferences_service()
    library_db = get_library_db()
    mbid_store = get_mbid_store()
    return PlexLibraryService(plex_repo, preferences_service, library_db, mbid_store)


@singleton
def get_plex_playback_service() -> "PlexPlaybackService":
    from services.plex_playback_service import PlexPlaybackService

    plex_repo = get_plex_repository()
    cache = get_cache()
    return PlexPlaybackService(plex_repo, cache)

"""Tier 3: repository providers and infrastructure services."""

from __future__ import annotations

import logging

import httpx

from core.config import get_settings
from infrastructure.http.client import get_http_client, get_listenbrainz_http_client

from ._registry import singleton
from .cache_providers import (
    get_cache,
    get_disk_cache,
    get_mbid_store,
    get_preferences_service,
)

logger = logging.getLogger(__name__)


def _get_configured_http_client() -> httpx.AsyncClient:
    settings = get_settings()
    advanced = get_preferences_service().get_advanced_settings()
    return get_http_client(
        settings,
        timeout=float(advanced.http_timeout),
        connect_timeout=float(advanced.http_connect_timeout),
        max_connections=advanced.http_max_connections,
    )


@singleton
def get_lidarr_repository() -> "LidarrRepository":
    from repositories.lidarr import LidarrRepository

    settings = get_settings()
    cache = get_cache()
    http_client = _get_configured_http_client()
    request_history_store = get_request_history_store()
    return LidarrRepository(settings, http_client, cache, request_history_store=request_history_store)


@singleton
def get_musicbrainz_repository() -> "MusicBrainzRepository":
    from repositories.musicbrainz_repository import MusicBrainzRepository

    cache = get_cache()
    preferences_service = get_preferences_service()
    http_client = _get_configured_http_client()
    return MusicBrainzRepository(http_client, cache, preferences_service)


@singleton
def get_wikidata_repository() -> "WikidataRepository":
    from repositories.wikidata_repository import WikidataRepository

    cache = get_cache()
    http_client = _get_configured_http_client()
    return WikidataRepository(http_client, cache)


@singleton
def get_listenbrainz_repository() -> "ListenBrainzRepository":
    from repositories.listenbrainz_repository import ListenBrainzRepository

    cache = get_cache()
    http_client = get_listenbrainz_http_client(
        settings=get_settings(),
        timeout=float(get_preferences_service().get_advanced_settings().http_timeout),
        connect_timeout=float(get_preferences_service().get_advanced_settings().http_connect_timeout),
    )
    preferences = get_preferences_service()
    lb_settings = preferences.get_listenbrainz_connection()
    return ListenBrainzRepository(
        http_client=http_client,
        cache=cache,
        username=lb_settings.username if lb_settings.enabled else "",
        user_token=lb_settings.user_token if lb_settings.enabled else "",
    )


@singleton
def get_jellyfin_repository() -> "JellyfinRepository":
    from repositories.jellyfin_repository import JellyfinRepository

    cache = get_cache()
    mbid_store = get_mbid_store()
    http_client = _get_configured_http_client()
    preferences = get_preferences_service()
    jf_settings = preferences.get_jellyfin_connection()
    return JellyfinRepository(
        http_client=http_client,
        cache=cache,
        base_url=jf_settings.jellyfin_url if jf_settings.enabled else "",
        api_key=jf_settings.api_key if jf_settings.enabled else "",
        user_id=jf_settings.user_id if jf_settings.enabled else "",
        mbid_store=mbid_store,
    )


@singleton
def get_navidrome_repository() -> "NavidromeRepository":
    from repositories.navidrome_repository import NavidromeRepository

    cache = get_cache()
    http_client = _get_configured_http_client()
    preferences = get_preferences_service()
    nd_settings = preferences.get_navidrome_connection_raw()
    repo = NavidromeRepository(http_client=http_client, cache=cache)
    if nd_settings.enabled:
        repo.configure(
            url=nd_settings.navidrome_url,
            username=nd_settings.username,
            password=nd_settings.password,
        )
    adv = preferences.get_advanced_settings()
    repo.configure_cache_ttls(
        list_ttl=getattr(adv, "cache_ttl_navidrome_albums", 300),
        search_ttl=getattr(adv, "cache_ttl_navidrome_search", 120),
        genres_ttl=getattr(adv, "cache_ttl_navidrome_genres", 3600),
        detail_ttl=getattr(adv, "cache_ttl_navidrome_albums", 300),
    )
    return repo


@singleton
def get_plex_repository() -> "PlexRepository":
    from repositories.plex_repository import PlexRepository

    cache = get_cache()
    http_client = _get_configured_http_client()
    preferences = get_preferences_service()
    plex_settings = preferences.get_plex_connection_raw()
    repo = PlexRepository(http_client=http_client, cache=cache)
    if plex_settings.enabled:
        client_id = preferences.get_setting("plex_client_id") or ""
        repo.configure(
            url=plex_settings.plex_url,
            token=plex_settings.plex_token,
            client_id=client_id,
        )
    adv = preferences.get_advanced_settings()
    repo.configure_cache_ttls(
        list_ttl=adv.cache_ttl_plex_albums,
        search_ttl=adv.cache_ttl_plex_search,
        genres_ttl=adv.cache_ttl_plex_genres,
        detail_ttl=adv.cache_ttl_plex_albums,
        stats_ttl=adv.cache_ttl_plex_stats,
    )
    return repo


@singleton
def get_youtube_repo() -> "YouTubeRepository":
    from repositories.youtube import YouTubeRepository

    http_client = _get_configured_http_client()
    preferences_service = get_preferences_service()
    yt_settings = preferences_service.get_youtube_connection()
    api_key = yt_settings.api_key.strip() if (yt_settings.enabled and yt_settings.api_enabled and yt_settings.has_valid_api_key()) else ""
    return YouTubeRepository(
        http_client=http_client,
        api_key=api_key,
        daily_quota_limit=yt_settings.daily_quota_limit,
    )


@singleton
def get_audiodb_repository() -> "AudioDBRepository":
    from repositories.audiodb_repository import AudioDBRepository

    settings = get_settings()
    http_client = _get_configured_http_client()
    preferences_service = get_preferences_service()
    return AudioDBRepository(
        http_client=http_client,
        preferences_service=preferences_service,
        api_key=settings.audiodb_api_key,
        premium=settings.audiodb_premium,
    )


@singleton
def get_audiodb_image_service() -> "AudioDBImageService":
    from services.audiodb_image_service import AudioDBImageService

    audiodb_repo = get_audiodb_repository()
    disk_cache = get_disk_cache()
    preferences_service = get_preferences_service()
    memory_cache = get_cache()
    return AudioDBImageService(
        audiodb_repo=audiodb_repo,
        disk_cache=disk_cache,
        preferences_service=preferences_service,
        memory_cache=memory_cache,
    )


@singleton
def get_audiodb_browse_queue() -> "AudioDBBrowseQueue":
    from services.audiodb_browse_queue import AudioDBBrowseQueue

    return AudioDBBrowseQueue()


@singleton
def get_lastfm_repository() -> "LastFmRepository":
    from repositories.lastfm_repository import LastFmRepository

    http_client = _get_configured_http_client()
    preferences = get_preferences_service()
    lf_settings = preferences.get_lastfm_connection()
    cache = get_cache()
    return LastFmRepository(
        http_client=http_client,
        cache=cache,
        api_key=lf_settings.api_key,
        shared_secret=lf_settings.shared_secret,
        session_key=lf_settings.session_key,
    )


@singleton
def get_playlist_repository() -> "PlaylistRepository":
    from repositories.playlist_repository import PlaylistRepository

    settings = get_settings()
    return PlaylistRepository(db_path=settings.library_db_path)


@singleton
def get_request_history_store() -> "RequestHistoryStore":
    from infrastructure.persistence.request_history import RequestHistoryStore
    from .cache_providers import get_persistence_write_lock

    settings = get_settings()
    return RequestHistoryStore(db_path=settings.library_db_path, write_lock=get_persistence_write_lock())


@singleton
def get_coverart_repository() -> "CoverArtRepository":
    from repositories.coverart_repository import CoverArtRepository

    settings = get_settings()
    advanced = get_preferences_service().get_advanced_settings()
    cache = get_cache()
    mb_repo = get_musicbrainz_repository()
    lidarr_repo = get_lidarr_repository()
    jellyfin_repo = get_jellyfin_repository()
    audiodb_service = get_audiodb_image_service()
    http_client = _get_configured_http_client()
    cache_dir = settings.cache_dir / "covers"
    return CoverArtRepository(
        http_client,
        cache,
        mb_repo,
        lidarr_repo,
        jellyfin_repo,
        audiodb_service=audiodb_service,
        cache_dir=cache_dir,
        cover_cache_max_size_mb=settings.cover_cache_max_size_mb,
        cover_memory_cache_max_entries=advanced.cover_memory_cache_max_entries,
        cover_memory_cache_max_bytes=advanced.cover_memory_cache_max_size_mb * 1024 * 1024,
        cover_non_monitored_ttl_seconds=advanced.cache_ttl_recently_viewed_bytes,
    )


@singleton
def get_github_repository() -> "GitHubRepository":
    from repositories.github_repository import GitHubRepository

    cache = get_cache()
    http_client = _get_configured_http_client()
    return GitHubRepository(http_client, cache)

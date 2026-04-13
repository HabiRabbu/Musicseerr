"""Slim HomeService facade that preserves the constructor signature and delegates to sub-services."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from api.v1.schemas.home import (
    HomeResponse,
    HomeGenre,
    HomeArtist,
    DiscoverPreview,
    HomeIntegrationStatus,
)
from api.v1.schemas.library import LibraryAlbum
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from services.preferences_service import PreferencesService
from services.home_transformers import HomeDataTransformers
from infrastructure.cache.cache_keys import DISCOVER_RESPONSE_PREFIX, HOME_RESPONSE_PREFIX
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.http.deduplication import deduplicate

from .integration_helpers import HomeIntegrationHelpers
from .section_builders import HomeSectionBuilders
from .genre_service import GenreService
from services.weekly_exploration_service import WeeklyExplorationService

logger = logging.getLogger(__name__)


class HomeService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        jellyfin_repo: JellyfinRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
        memory_cache: CacheInterface | None = None,
        lastfm_repo: LastFmRepositoryProtocol | None = None,
        audiodb_image_service: Any = None,
        cache_dir: Path | None = None,
    ):
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._preferences = preferences_service
        self._memory_cache = memory_cache
        self._lfm_repo = lastfm_repo
        self._audiodb_image_service = audiodb_image_service
        self._transformers = HomeDataTransformers(jellyfin_repo)

        self._helpers = HomeIntegrationHelpers(preferences_service)
        self._builders = HomeSectionBuilders(self._transformers)
        self._genre = GenreService(
            musicbrainz_repo, memory_cache, audiodb_image_service,
            cache_dir=cache_dir, preferences_service=preferences_service,
        )
        self._weekly_exploration = WeeklyExplorationService(listenbrainz_repo, musicbrainz_repo)

    def clear_genre_disk_cache(self) -> int:
        """Delegate to GenreService to delete genre section files from disk."""
        return self._genre.clear_disk_cache()

    def _resolve_source(self, source: str | None = None) -> str:
        return self._helpers.resolve_source(source)

    def _build_service_prompts(self, lb_enabled, lidarr_configured, lfm_enabled):
        return self._builders.build_service_prompts(lb_enabled, lidarr_configured, lfm_enabled)

    def get_integration_status(self) -> HomeIntegrationStatus:
        return HomeIntegrationStatus(
            listenbrainz=self._helpers.is_listenbrainz_enabled(),
            jellyfin=self._helpers.is_jellyfin_enabled(),
            lidarr=self._helpers.is_lidarr_configured(),
            youtube=self._helpers.is_youtube_enabled(),
            youtube_api=self._helpers.is_youtube_api_enabled(),
            localfiles=self._helpers.is_local_files_enabled(),
            lastfm=self._helpers.is_lastfm_enabled(),
            navidrome=self._helpers.is_navidrome_enabled(),
            plex=self._helpers.is_plex_enabled(),
        )

    async def get_genre_artist(
        self, genre_name: str, exclude_mbids: set[str] | None = None
    ) -> str | None:
        return await self._genre.get_genre_artist(genre_name, exclude_mbids)

    async def get_genre_artists_batch(self, genres: list[str]) -> dict[str, str | None]:
        return await self._genre.get_genre_artists_batch(genres)

    def _get_home_cache_key(self, source: str | None = None) -> str:
        resolved = self._helpers.resolve_source(source)
        lb_enabled = self._helpers.is_listenbrainz_enabled()
        lfm_enabled = self._helpers.is_lastfm_enabled()
        lb_username = self._helpers.get_listenbrainz_username() or ""
        lfm_username = self._helpers.get_lastfm_username() or ""
        return f"{HOME_RESPONSE_PREFIX}{resolved}:{lb_enabled}:{lfm_enabled}:{lb_username}:{lfm_username}"

    async def get_cached_home_data(self, source: str | None = None) -> HomeResponse | None:
        if not self._memory_cache:
            return None
        cache_key = self._get_home_cache_key(source)
        return await self._memory_cache.get(cache_key)

    @deduplicate(lambda self, source=None: self._get_home_cache_key(source))
    async def get_home_data(self, source: str | None = None) -> HomeResponse:
        HOME_CACHE_TTL = 300
        resolved_source = self._helpers.resolve_source(source)

        if self._memory_cache:
            cache_key = self._get_home_cache_key(source)
            cached = await self._memory_cache.get(cache_key)
            if cached is not None:
                if not cached.genre_artists:
                    genre_section = await self._genre.get_cached_genre_section(resolved_source)
                    if genre_section:
                        from infrastructure.serialization import clone_with_updates
                        cached = clone_with_updates(cached, {
                            "genre_artists": genre_section[0],
                            "genre_artist_images": genre_section[1],
                        })
                        if cached.genre_list and cached.genre_list.items:
                            cur_names = [g.name for g in cached.genre_list.items[:20] if isinstance(g, HomeGenre)]
                            missing = [n for n in cur_names if n not in genre_section[0]]
                            if missing:
                                asyncio.create_task(
                                    self._genre.build_and_cache_genre_section(resolved_source, cur_names)
                                )
                return cached

        integration_status = self.get_integration_status()
        lb_enabled = integration_status.listenbrainz
        lidarr_configured = integration_status.lidarr
        lfm_enabled = integration_status.lastfm
        username = self._helpers.get_listenbrainz_username()
        lfm_username = self._helpers.get_lastfm_username()

        tasks: dict[str, Any] = {}

        if resolved_source == "listenbrainz":
            tasks["lb_trending_artists"] = self._lb_repo.get_sitewide_top_artists(count=20)
            tasks["lb_trending_albums"] = self._lb_repo.get_sitewide_top_release_groups(count=20)
        elif resolved_source == "lastfm" and self._lfm_repo and lfm_enabled:
            tasks["lfm_global_top_artists"] = self._lfm_repo.get_global_top_artists(limit=20)
            if lfm_username:
                tasks["lfm_top_albums"] = self._lfm_repo.get_user_top_albums(
                    lfm_username, period="1month", limit=20
                )
            else:
                logger.warning(
                    "Last.fm enabled as home source but username is missing; skipping top album fetch"
                )

        if lidarr_configured:
            tasks["library_albums"] = self._lidarr_repo.get_library()
            tasks["library_artists"] = self._lidarr_repo.get_artists_from_library()
            tasks["recently_imported"] = self._lidarr_repo.get_recently_imported(limit=15)

        if resolved_source == "listenbrainz" and lb_enabled and username:
            lb_settings = self._preferences.get_listenbrainz_connection()
            self._lb_repo.configure(username=username, user_token=lb_settings.user_token)
            tasks["lb_listens"] = self._lb_repo.get_user_listens(count=20)
            tasks["lb_loved"] = self._lb_repo.get_user_loved_recordings(count=20)
            tasks["lb_genres"] = self._lb_repo.get_user_genre_activity(username)
            tasks["lb_user_top_rgs"] = self._lb_repo.get_user_top_release_groups(
                username=username, range_="this_month", count=20
            )
            tasks["lb_weekly_exploration"] = self._weekly_exploration.build_section(username)
        elif resolved_source == "lastfm" and self._lfm_repo and lfm_enabled and lfm_username:
            tasks["lfm_recent"] = self._lfm_repo.get_user_recent_tracks(
                lfm_username, limit=20
            )
            tasks["lfm_loved"] = self._lfm_repo.get_user_loved_tracks(
                lfm_username, limit=20
            )

        results = await self._helpers.execute_tasks(tasks)

        library_albums: list[LibraryAlbum] = results.get("library_albums") or []
        library_artists: list[dict] = results.get("library_artists") or []
        recently_imported: list[LibraryAlbum] = results.get("recently_imported") or []
        library_artist_mbids = {
            a.get("mbid", "").lower() for a in library_artists if a.get("mbid")
        }
        library_album_mbids = {
            (a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id
        }

        response = HomeResponse(integration_status=integration_status)

        response.recently_added = self._builders.build_recently_added_section(recently_imported)
        response.library_artists = self._builders.build_library_artists_section(library_artists)
        response.library_albums = self._builders.build_library_albums_section(library_albums)

        if resolved_source == "listenbrainz":
            response.trending_artists = self._builders.build_trending_artists_section(
                results, library_artist_mbids
            )
            response.popular_albums = self._builders.build_popular_albums_section(
                results, library_album_mbids
            )
            response.your_top_albums = self._builders.build_lb_user_top_albums_section(
                results, library_album_mbids
            )
            response.recently_played = self._builders.build_listenbrainz_recent_section(results)
            response.favorite_artists = self._builders.build_listenbrainz_favorites_section(results)
            response.weekly_exploration = results.get("lb_weekly_exploration")
        elif resolved_source == "lastfm":
            response.trending_artists = self._builders.build_lastfm_trending_section(
                results, library_artist_mbids
            )
            response.your_top_albums = self._builders.build_lastfm_top_albums_section(
                results, library_album_mbids
            )
            response.recently_played = self._builders.build_lastfm_recent_section(results)
            response.favorite_artists = self._builders.build_lastfm_favorites_section(results)

        response.genre_list = self._builders.build_genre_list_section(
            library_albums,
            results.get("lb_genres") if resolved_source == "listenbrainz" else None,
        )

        if response.genre_list and response.genre_list.items:
            genre_names = [
                g.name for g in response.genre_list.items[:20]
                if isinstance(g, HomeGenre)
            ]
            cached_section = await self._genre.get_cached_genre_section(resolved_source)
            if cached_section:
                response.genre_artists, response.genre_artist_images = cached_section
                missing = [n for n in genre_names if n not in cached_section[0]]
                if missing:
                    asyncio.create_task(
                        self._genre.build_and_cache_genre_section(resolved_source, genre_names)
                    )
            elif genre_names:
                asyncio.create_task(
                    self._genre.build_and_cache_genre_section(resolved_source, genre_names)
                )

        response.service_prompts = self._builders.build_service_prompts(
            lb_enabled,
            lidarr_configured,
            lfm_enabled,
        )

        response.discover_preview = await self._build_discover_preview()

        if self._memory_cache:
            cache_key = self._get_home_cache_key(source)
            await self._memory_cache.set(cache_key, response, HOME_CACHE_TTL)

        return response

    async def _build_discover_preview(self) -> DiscoverPreview | None:
        if not self._memory_cache:
            return None
        try:
            from api.v1.schemas.discover import DiscoverResponse as DR
            resolved = self._helpers.resolve_source(None)
            cache_key = f"{DISCOVER_RESPONSE_PREFIX}{resolved}"
            cached = await self._memory_cache.get(cache_key)
            if not cached or not isinstance(cached, DR):
                return None
            if not cached.because_you_listen_to:
                return None
            first = cached.because_you_listen_to[0]
            preview_items = [
                item for item in first.section.items[:15]
                if isinstance(item, HomeArtist)
            ]
            return DiscoverPreview(
                seed_artist=first.seed_artist,
                seed_artist_mbid=first.seed_artist_mbid,
                items=preview_items,
            )
        except Exception as e:  # noqa: BLE001
            return None

    async def _resolve_release_mbids(self, release_ids: list[str]) -> dict[str, str]:
        if not release_ids:
            return {}
        import asyncio as _asyncio
        tasks = [self._mb_repo.get_release_group_id_from_release(rid) for rid in release_ids]
        results = await _asyncio.gather(*tasks, return_exceptions=True)
        rg_map: dict[str, str] = {}
        for rid, rg_id in zip(release_ids, results):
            if isinstance(rg_id, str) and rg_id:
                rg_map[rid] = rg_id
        return rg_map

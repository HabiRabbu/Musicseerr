import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from api.v1.schemas.discover import (
    DiscoverResponse,
    BecauseYouListenTo,
    DiscoverQueueItemLight,
    DiscoverQueueEnrichment,
    DiscoverQueueResponse,
    DiscoverIntegrationStatus,
    DiscoverIgnoredRelease,
    QueueSettings,
)
from api.v1.schemas.home import (
    HomeSection,
    HomeArtist,
    HomeAlbum,
    HomeGenre,
    ServicePrompt,
    DiscoverPreview,
)
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from services.preferences_service import PreferencesService
from services.home_transformers import HomeDataTransformers
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cover_urls import prefer_artist_cover_url
from infrastructure.serialization import clone_with_updates
from infrastructure.validators import clean_lastfm_bio, strip_html_tags
from repositories.listenbrainz_models import ListenBrainzArtist

logger = logging.getLogger(__name__)

DISCOVER_CACHE_KEY = "discover_response"
DISCOVER_CACHE_TTL = 43200  # 12 hours
REDISCOVER_PLAY_THRESHOLD = 5
REDISCOVER_MONTHS_AGO = 3
MISSING_ESSENTIALS_MIN_ALBUMS = 3
MISSING_ESSENTIALS_MAX_PER_ARTIST = 3
VARIOUS_ARTISTS_MBID = "89ad4ac3-39f7-470e-963a-56509c546377"


class DiscoverService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        jellyfin_repo: JellyfinRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
        memory_cache: CacheInterface | None = None,
        library_cache: LibraryCache | None = None,
        wikidata_repo: Any = None,
        lastfm_repo: LastFmRepositoryProtocol | None = None,
    ):
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._preferences = preferences_service
        self._memory_cache = memory_cache
        self._library_cache = library_cache
        self._wikidata_repo = wikidata_repo
        self._lfm_repo = lastfm_repo
        self._transformers = HomeDataTransformers(jellyfin_repo)
        self._building = False
        self._enrich_in_flight: dict[str, asyncio.Future[DiscoverQueueEnrichment]] = {}

    def _is_listenbrainz_enabled(self) -> bool:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.enabled and bool(lb_settings.username)

    def _is_jellyfin_enabled(self) -> bool:
        jf_settings = self._preferences.get_jellyfin_connection()
        return jf_settings.enabled and bool(jf_settings.jellyfin_url) and bool(jf_settings.api_key)

    def _is_lidarr_configured(self) -> bool:
        lidarr_connection = self._preferences.get_lidarr_connection()
        return bool(lidarr_connection.lidarr_url) and bool(lidarr_connection.lidarr_api_key)

    def _is_youtube_enabled(self) -> bool:
        yt_settings = self._preferences.get_youtube_connection()
        return yt_settings.enabled and bool(yt_settings.api_key)

    def _is_lastfm_enabled(self) -> bool:
        return self._preferences.is_lastfm_enabled()

    def _get_listenbrainz_username(self) -> str | None:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.username if lb_settings.enabled else None

    def _get_lastfm_username(self) -> str | None:
        lf_settings = self._preferences.get_lastfm_connection()
        return lf_settings.username if lf_settings.enabled else None

    def resolve_source(self, source: str | None) -> str:
        if source in ("listenbrainz", "lastfm"):
            resolved = source
        else:
            resolved = self._preferences.get_primary_music_source().source
        lb_enabled = self._is_listenbrainz_enabled()
        lfm_enabled = self._is_lastfm_enabled()
        if resolved == "listenbrainz" and not lb_enabled and lfm_enabled:
            return "lastfm"
        if resolved == "lastfm" and not lfm_enabled and lb_enabled:
            return "listenbrainz"
        return resolved

    def _get_queue_settings(self) -> QueueSettings:
        adv = self._preferences.get_advanced_settings()
        return QueueSettings(
            queue_size=adv.discover_queue_size,
            queue_ttl=adv.discover_queue_ttl,
            seed_artists=adv.discover_queue_seed_artists,
            wildcard_slots=adv.discover_queue_wildcard_slots,
            similar_artists_limit=adv.discover_queue_similar_artists_limit,
            albums_per_similar=adv.discover_queue_albums_per_similar,
            enrich_ttl=adv.discover_queue_enrich_ttl,
            lastfm_mbid_max_lookups=adv.discover_queue_lastfm_mbid_max_lookups,
        )

    def _get_discover_cache_key(self, source: str | None = None) -> str:
        resolved = self.resolve_source(source)
        return f"{DISCOVER_CACHE_KEY}:{resolved}"

    async def get_discover_data(self, source: str | None = None) -> DiscoverResponse:
        resolved_source = self.resolve_source(source)
        if self._memory_cache:
            cache_key = self._get_discover_cache_key(source)
            cached = await self._memory_cache.get(cache_key)
            if cached is not None:
                if isinstance(cached, DiscoverResponse):
                    return clone_with_updates(cached, {"refreshing": self._building})
        if not self._building:
            asyncio.create_task(self.warm_cache(source=resolved_source))
        return DiscoverResponse(
            integration_status=self._get_integration_status(),
            service_prompts=self._build_service_prompts(),
            refreshing=True,
        )

    def _get_integration_status(self) -> DiscoverIntegrationStatus:
        return DiscoverIntegrationStatus(
            listenbrainz=self._is_listenbrainz_enabled(),
            jellyfin=self._is_jellyfin_enabled(),
            lidarr=self._is_lidarr_configured(),
            youtube=self._is_youtube_enabled(),
            lastfm=self._is_lastfm_enabled(),
        )

    async def get_discover_preview(self) -> DiscoverPreview | None:
        if not self._memory_cache:
            return None
        resolved = self.resolve_source(None)
        cache_key = self._get_discover_cache_key(resolved)
        cached = await self._memory_cache.get(cache_key)
        if not cached or not isinstance(cached, DiscoverResponse):
            return None
        if not cached.because_you_listen_to:
            return None
        first = cached.because_you_listen_to[0]
        preview_items = [
            item for item in first.section.items[:5]
            if isinstance(item, HomeArtist)
        ]
        return DiscoverPreview(
            seed_artist=first.seed_artist,
            seed_artist_mbid=first.seed_artist_mbid,
            items=preview_items,
        )

    async def refresh_discover_data(self) -> None:
        if self._building:
            return
        asyncio.create_task(self.warm_cache())

    async def warm_cache(self, source: str | None = None) -> None:
        if self._building:
            return
        self._building = True
        try:
            resolved = self.resolve_source(source)
            response = await self.build_discover_data(source=resolved)
            if self._memory_cache and self._has_meaningful_content(response):
                cache_key = self._get_discover_cache_key(resolved)
                await self._memory_cache.set(cache_key, response, DISCOVER_CACHE_TTL)
                logger.info("Discover data built and cached for source=%s", resolved)
            elif not self._has_meaningful_content(response):
                logger.warning("Discover build produced no meaningful content, keeping existing cache")
        except Exception as e:
            logger.error(f"Failed to build discover data: {e}")
        finally:
            self._building = False

    def _has_meaningful_content(self, response: DiscoverResponse) -> bool:
        return bool(
            response.because_you_listen_to
            or response.fresh_releases
            or response.globally_trending
            or response.artists_you_might_like
            or response.popular_in_your_genres
            or response.missing_essentials
            or response.rediscover
            or response.lastfm_weekly_artist_chart
            or response.lastfm_weekly_album_chart
            or response.lastfm_recent_scrobbles
        )

    async def build_discover_data(self, source: str | None = None) -> DiscoverResponse:
        resolved_source = self.resolve_source(source)
        lb_enabled = self._is_listenbrainz_enabled()
        jf_enabled = self._is_jellyfin_enabled()
        lidarr_configured = self._is_lidarr_configured()
        lfm_enabled = self._is_lastfm_enabled()
        username = self._get_listenbrainz_username()
        lfm_username = self._get_lastfm_username()

        if lb_enabled and username:
            lb_settings = self._preferences.get_listenbrainz_connection()
            self._lb_repo.configure(username=username, user_token=lb_settings.user_token)

        if jf_enabled:
            jf_settings = self._preferences.get_jellyfin_connection()
            self._jf_repo.configure(
                base_url=jf_settings.jellyfin_url,
                api_key=jf_settings.api_key,
                user_id=jf_settings.user_id,
            )

        library_mbids = await self._get_library_mbids(lidarr_configured)

        seed_artists = await self._get_seed_artists(
            lb_enabled, username, jf_enabled,
            resolved_source=resolved_source,
            lfm_enabled=lfm_enabled,
            lfm_username=lfm_username,
        )

        tasks: dict[str, Any] = {}

        for i, seed in enumerate(seed_artists[:3]):
            mbid = seed.artist_mbids[0] if hasattr(seed, 'artist_mbids') and seed.artist_mbids else getattr(seed, 'artist_mbid', None)
            if mbid:
                if resolved_source == "lastfm" and self._lfm_repo and lfm_enabled:
                    tasks[f"similar_{i}"] = self._lfm_repo.get_similar_artists(
                        seed.artist_name, mbid=mbid, limit=20
                    )
                else:
                    tasks[f"similar_{i}"] = self._lb_repo.get_similar_artists(mbid, max_similar=20)

        if resolved_source == "listenbrainz":
            tasks["lb_trending"] = self._lb_repo.get_sitewide_top_artists(count=20)
        elif resolved_source == "lastfm" and self._lfm_repo and lfm_enabled:
            tasks["lfm_global_top"] = self._lfm_repo.get_global_top_artists(limit=20)

        if self._lfm_repo and lfm_enabled and lfm_username:
            tasks["lfm_weekly_artists"] = self._lfm_repo.get_user_weekly_artist_chart(
                lfm_username
            )
            tasks["lfm_weekly_albums"] = self._lfm_repo.get_user_weekly_album_chart(
                lfm_username
            )
            tasks["lfm_recent"] = self._lfm_repo.get_user_recent_tracks(
                lfm_username, limit=20
            )

        if resolved_source == "listenbrainz" and lb_enabled and username:
            tasks["lb_fresh"] = self._lb_repo.get_user_fresh_releases()
            tasks["lb_genres"] = self._lb_repo.get_user_genre_activity(username)
        elif resolved_source == "lastfm" and self._lfm_repo and lfm_enabled and lfm_username:
            tasks["lfm_user_top_artists_for_genres"] = self._lfm_repo.get_user_top_artists(
                lfm_username, period="3month", limit=5
            )

        if jf_enabled:
            tasks["jf_most_played"] = self._jf_repo.get_most_played_artists(limit=50)

        if lidarr_configured:
            tasks["library_artists"] = self._lidarr_repo.get_artists_from_library()
            tasks["library_albums"] = self._lidarr_repo.get_library()

        results = await self._execute_tasks(tasks)

        logger.info(
            "Discover data fetch results: %s",
            {k: "ok" if v is not None else "empty" for k, v in results.items()},
        )

        response = DiscoverResponse(
            integration_status=self._get_integration_status(),
        )

        seen_artist_mbids: set[str] = set()

        response.because_you_listen_to = self._build_because_sections(
            seed_artists, results, library_mbids, seen_artist_mbids,
            resolved_source=resolved_source,
        )
        logger.info("because_you_listen_to: %d sections", len(response.because_you_listen_to))

        response.fresh_releases = self._build_fresh_releases(results, library_mbids)

        post_tasks = {
            "missing_essentials": self._build_missing_essentials(results, library_mbids),
            "lastfm_weekly_album_chart": self._build_lastfm_weekly_album_chart(
                results, library_mbids
            ),
            "lastfm_recent_scrobbles": self._build_lastfm_recent_scrobbles(
                results, library_mbids
            ),
        }
        post_results = await self._execute_tasks(post_tasks)
        response.missing_essentials = post_results.get("missing_essentials")

        response.rediscover = self._build_rediscover(results, library_mbids, jf_enabled)

        response.artists_you_might_like = self._build_artists_you_might_like(
            seed_artists, results, library_mbids, seen_artist_mbids,
            resolved_source=resolved_source,
        )

        response.popular_in_your_genres = await self._build_popular_in_genres(
            results, library_mbids, seen_artist_mbids,
            resolved_source=resolved_source,
        )

        response.genre_list = self._build_genre_list(results, lb_enabled)

        if response.genre_list and response.genre_list.items:
            genre_names = [
                g.name for g in response.genre_list.items[:20]
                if isinstance(g, HomeGenre)
            ]
            if genre_names:
                genre_tasks = {g: self._get_genre_artist(g) for g in genre_names}
                genre_results = await self._execute_tasks(genre_tasks)
                response.genre_artists = {g: mbid for g, mbid in genre_results.items()}

        if resolved_source == "lastfm":
            response.globally_trending = self._build_lastfm_globally_trending(
                results, library_mbids, seen_artist_mbids
            )
        else:
            response.globally_trending = self._build_globally_trending(
                results, library_mbids, seen_artist_mbids
            )

        response.lastfm_weekly_artist_chart = self._build_lastfm_weekly_artist_chart(
            results, library_mbids, seen_artist_mbids
        )
        response.lastfm_weekly_album_chart = post_results.get("lastfm_weekly_album_chart")
        response.lastfm_recent_scrobbles = post_results.get("lastfm_recent_scrobbles")

        response.service_prompts = self._build_service_prompts()

        sections_status = {
            "because": len(response.because_you_listen_to),
            "fresh_releases": response.fresh_releases is not None,
            "missing_essentials": response.missing_essentials is not None,
            "rediscover": response.rediscover is not None,
            "artists_you_might_like": response.artists_you_might_like is not None,
            "popular_in_genres": response.popular_in_your_genres is not None,
            "genre_list": response.genre_list is not None,
            "globally_trending": response.globally_trending is not None,
            "lastfm_weekly_artist_chart": getattr(response, "lastfm_weekly_artist_chart", None) is not None,
            "lastfm_weekly_album_chart": getattr(response, "lastfm_weekly_album_chart", None) is not None,
            "lastfm_recent_scrobbles": getattr(response, "lastfm_recent_scrobbles", None) is not None,
        }
        logger.info("Discover build complete (source=%s): %s", resolved_source, sections_status)

        return response

    async def _get_library_mbids(self, lidarr_configured: bool) -> set[str]:
        if not lidarr_configured:
            return set()
        try:
            artists = await self._lidarr_repo.get_artists_from_library()
            return {a.get("mbid", "").lower() for a in artists if a.get("mbid")}
        except Exception:
            return set()

    async def _get_seed_artists(
        self,
        lb_enabled: bool,
        username: str | None,
        jf_enabled: bool,
        resolved_source: str = "listenbrainz",
        lfm_enabled: bool = False,
        lfm_username: str | None = None,
    ) -> list[ListenBrainzArtist]:
        seeds: list[ListenBrainzArtist] = []
        seen_mbids: set[str] = set()

        if resolved_source == "lastfm" and lfm_enabled and lfm_username and self._lfm_repo:
            try:
                lfm_artists = await self._lfm_repo.get_user_top_artists(
                    lfm_username, period="3month", limit=10
                )
                for a in lfm_artists:
                    if len(seeds) >= 3:
                        break
                    mbid = a.mbid
                    if mbid and mbid not in seen_mbids:
                        seeds.append(
                            ListenBrainzArtist(
                                artist_name=a.name,
                                listen_count=a.playcount,
                                artist_mbids=[mbid],
                            )
                        )
                        seen_mbids.add(mbid)
            except Exception as e:
                logger.warning("Failed to get Last.fm seed artists: %s", e)

        if resolved_source != "lastfm" and len(seeds) < 3 and lb_enabled and username:
            for range_ in ("this_week", "this_month"):
                if len(seeds) >= 3:
                    break
                try:
                    artists = await self._lb_repo.get_user_top_artists(count=10, range_=range_)
                    for a in artists:
                        if len(seeds) >= 3:
                            break
                        mbid = a.artist_mbids[0] if a.artist_mbids else None
                        if mbid and mbid not in seen_mbids:
                            seeds.append(a)
                            seen_mbids.add(mbid)
                except Exception as e:
                    logger.warning(f"Failed to get LB top artists ({range_}): {e}")

        if resolved_source != "lastfm" and len(seeds) < 3 and jf_enabled:
            for fetch_fn in (
                lambda: self._jf_repo.get_most_played_artists(limit=10),
                lambda: self._jf_repo.get_favorite_artists(limit=10),
            ):
                if len(seeds) >= 3:
                    break
                try:
                    jf_items = await fetch_fn()
                    for item in jf_items:
                        if len(seeds) >= 3:
                            break
                        mbid = None
                        if item.provider_ids:
                            mbid = item.provider_ids.get("MusicBrainzArtist")
                        if mbid and mbid not in seen_mbids:
                            seeds.append(ListenBrainzArtist(
                                artist_name=item.artist_name or item.name,
                                listen_count=item.play_count,
                                artist_mbids=[mbid],
                            ))
                            seen_mbids.add(mbid)
                except Exception as e:
                    logger.warning(f"Failed to get Jellyfin seed artists: {e}")
                    continue

        logger.info(
            "Seed artists found: %d — %s",
            len(seeds),
            [(s.artist_name, s.artist_mbids[0][:8] if s.artist_mbids else "?") for s in seeds],
        )
        return seeds

    @staticmethod
    def _normalize_mbid(mbid: str | None) -> str | None:
        if not mbid:
            return None
        normalized = mbid.strip().lower()
        return normalized or None

    async def _resolve_lastfm_release_group_mbids(
        self,
        album_mbids: list[str],
        *,
        max_lookups: int = 10,
        allow_passthrough: bool = True,
        resolver_cache: dict[str, str | None] | None = None,
    ) -> dict[str, str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for mbid in album_mbids:
            mbid_normalized = self._normalize_mbid(mbid)
            if not mbid_normalized or mbid_normalized in seen:
                continue
            normalized.append(mbid_normalized)
            seen.add(mbid_normalized)

        if not normalized:
            return {}

        cache = resolver_cache if resolver_cache is not None else {}
        resolved: dict[str, str] = {}
        pending: list[str] = []

        for mbid in normalized:
            if mbid in cache:
                cached_value = cache[mbid]
                if cached_value:
                    resolved[mbid] = cached_value
                elif allow_passthrough:
                    resolved[mbid] = mbid
                continue
            pending.append(mbid)

        if pending and self._library_cache:
            try:
                persisted = await self._library_cache.get_mbid_resolution_map(pending)
                still_pending: list[str] = []
                for mbid in pending:
                    if mbid in persisted:
                        rg_mbid = persisted[mbid]
                        cache[mbid] = rg_mbid
                        if rg_mbid:
                            resolved[mbid] = rg_mbid
                        elif allow_passthrough:
                            resolved[mbid] = mbid
                    else:
                        still_pending.append(mbid)
                pending = still_pending
            except Exception:
                logger.debug("Failed to load MBID resolution from persistent cache")

        if not pending:
            return resolved

        new_resolutions: dict[str, str | None] = {}

        lookup_mbids = pending[:max_lookups]
        skipped_mbids = pending[max_lookups:]
        for mbid in skipped_mbids:
            if allow_passthrough:
                resolved[mbid] = mbid
                cache[mbid] = mbid
            else:
                cache[mbid] = None

        release_results = await asyncio.gather(
            *[self._mb_repo.get_release_group_id_from_release(mbid) for mbid in lookup_mbids],
            return_exceptions=True,
        )
        unresolved: list[str] = []

        for mbid, result in zip(lookup_mbids, release_results):
            if isinstance(result, Exception):
                unresolved.append(mbid)
                continue
            rg_mbid = self._normalize_mbid(result)
            if rg_mbid:
                resolved[mbid] = rg_mbid
                cache[mbid] = rg_mbid
                new_resolutions[mbid] = rg_mbid
            else:
                unresolved.append(mbid)

        if not unresolved:
            if new_resolutions and self._library_cache:
                try:
                    await self._library_cache.save_mbid_resolution_map(new_resolutions)
                except Exception:
                    logger.debug("Failed to persist MBID resolutions")
            return resolved

        rg_checks = await asyncio.gather(
            *[
                self._mb_repo.get_release_group_by_id(mbid, includes=["artist-credits"])
                for mbid in unresolved
            ],
            return_exceptions=True,
        )

        for mbid, result in zip(unresolved, rg_checks):
            if isinstance(result, Exception):
                if allow_passthrough:
                    resolved[mbid] = mbid
                    cache[mbid] = mbid
                else:
                    cache[mbid] = None
                continue
            if isinstance(result, dict) and result.get("id"):
                resolved[mbid] = mbid
                cache[mbid] = mbid
                new_resolutions[mbid] = mbid
            elif allow_passthrough:
                resolved[mbid] = mbid
                cache[mbid] = mbid
            else:
                cache[mbid] = None
                new_resolutions[mbid] = None

        if new_resolutions and self._library_cache:
            try:
                await self._library_cache.save_mbid_resolution_map(new_resolutions)
            except Exception:
                logger.debug("Failed to persist MBID resolutions")

        return resolved

    async def _lastfm_albums_to_queue_items(
        self,
        artist_albums_pairs: list[tuple[Any, list]],
        *,
        exclude: set[str] | None = None,
        target: int,
        reason: str,
        is_wildcard: bool = False,
        resolver_cache: dict[str, str | None] | None = None,
        use_album_artist_name: bool = True,
    ) -> list[DiscoverQueueItemLight]:
        all_album_mbids: list[str] = []
        for _, albums in artist_albums_pairs:
            all_album_mbids.extend(a.mbid for a in albums if a.mbid)
        rg_mbid_map = await self._resolve_lastfm_release_group_mbids(
            all_album_mbids, resolver_cache=resolver_cache,
        )
        items: list[DiscoverQueueItemLight] = []
        seen_rg_mbids: set[str] = {mbid.lower() for mbid in (exclude or set())}
        for artist, albums in artist_albums_pairs:
            if len(items) >= target:
                break
            artist_mbid = self._normalize_mbid(artist.mbid)
            for album in albums:
                if len(items) >= target:
                    break
                raw_album_mbid = self._normalize_mbid(album.mbid)
                if not raw_album_mbid:
                    continue
                rg_mbid = rg_mbid_map.get(raw_album_mbid)
                if not rg_mbid:
                    continue
                rg_mbid_lower = rg_mbid.lower()
                if rg_mbid_lower in seen_rg_mbids:
                    continue
                artist_name = (album.artist_name or artist.name) if use_album_artist_name else artist.name
                items.append(DiscoverQueueItemLight(
                    release_group_mbid=rg_mbid,
                    album_name=album.name,
                    artist_name=artist_name,
                    artist_mbid=artist_mbid or "",
                    cover_url=f"/api/covers/release-group/{rg_mbid}?size=500",
                    recommendation_reason=reason,
                    is_wildcard=is_wildcard,
                    in_library=False,
                ))
                seen_rg_mbids.add(rg_mbid_lower)
        return items

    def _build_because_sections(
        self,
        seed_artists: list,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
        resolved_source: str = "listenbrainz",
    ) -> list[BecauseYouListenTo]:
        sections: list[BecauseYouListenTo] = []

        for i, seed in enumerate(seed_artists[:3]):
            similar = results.get(f"similar_{i}")
            if not similar:
                continue

            seed_name = getattr(seed, 'artist_name', 'Unknown')
            seed_mbid = ""
            if hasattr(seed, 'artist_mbids') and seed.artist_mbids:
                seed_mbid = seed.artist_mbids[0]
            elif hasattr(seed, 'artist_mbid'):
                seed_mbid = seed.artist_mbid

            items: list[HomeArtist] = []
            for artist in similar:
                mbid = getattr(artist, 'artist_mbid', None) or getattr(artist, 'mbid', None)
                name = getattr(artist, 'artist_name', None) or getattr(artist, 'name', '')
                listen_count = getattr(artist, 'listen_count', None) or getattr(artist, 'playcount', 0)
                if not mbid:
                    continue
                if mbid.lower() in seen_artist_mbids:
                    continue
                items.append(HomeArtist(
                    mbid=mbid,
                    name=name,
                    listen_count=listen_count,
                    in_library=mbid.lower() in library_mbids,
                ))
                seen_artist_mbids.add(mbid.lower())

            if not items:
                continue

            min_unique = 3
            if len(items) < min_unique and len(sections) > 0:
                continue

            source_label = "lastfm" if resolved_source == "lastfm" else "listenbrainz"
            sections.append(BecauseYouListenTo(
                seed_artist=seed_name,
                seed_artist_mbid=seed_mbid,
                listen_count=getattr(seed, 'listen_count', 0),
                section=HomeSection(
                    title=f"Because You Listen To {seed_name}",
                    type="artists",
                    items=items[:15],
                    source=source_label,
                ),
            ))

        return sections

    def _build_fresh_releases(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        releases = results.get("lb_fresh")
        if not releases:
            return None
        items: list[HomeAlbum] = []
        for r in releases[:15]:
            try:
                if isinstance(r, dict):
                    mbid = r.get("release_group_mbid", "")
                    artist_mbids = r.get("artist_mbids", [])
                    items.append(HomeAlbum(
                        mbid=mbid,
                        name=r.get("title", r.get("release_group_name", "Unknown")),
                        artist_name=r.get("artist_credit_name", r.get("artist_name", "")),
                        artist_mbid=artist_mbids[0] if artist_mbids else None,
                        listen_count=r.get("listen_count"),
                        in_library=mbid.lower() in library_mbids if isinstance(mbid, str) and mbid else False,
                    ))
                else:
                    items.append(self._transformers.lb_release_to_home(r, library_mbids))
            except Exception as e:
                logger.debug(f"Skipping fresh release item: {e}")
                continue
        if not items:
            return None
        return HomeSection(
            title="Fresh Releases For You",
            type="albums",
            items=items,
            source="listenbrainz",
        )

    async def _build_missing_essentials(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        library_artists = results.get("library_artists") or []
        library_albums = results.get("library_albums") or []

        if not library_artists or not library_albums:
            return None

        from collections import Counter
        artist_album_counts: Counter[str] = Counter()
        for album in library_albums:
            artist_mbid = getattr(album, 'artist_mbid', None)
            if artist_mbid:
                artist_album_counts[artist_mbid.lower()] += 1

        library_album_mbids = set()
        for album in library_albums:
            mbid = getattr(album, 'musicbrainz_id', None)
            if mbid:
                library_album_mbids.add(mbid.lower())

        qualifying_artists = [
            (mbid, count) for mbid, count in artist_album_counts.items()
            if count >= MISSING_ESSENTIALS_MIN_ALBUMS
        ]
        qualifying_artists.sort(key=lambda x: -x[1])

        semaphore = asyncio.Semaphore(3)

        async def _fetch_artist_missing(artist_mbid: str) -> list[HomeAlbum]:
            try:
                async with semaphore:
                    top_releases = await self._lb_repo.get_artist_top_release_groups(
                        artist_mbid, count=10
                    )
            except Exception as e:
                logger.debug(f"Failed to get releases for artist {artist_mbid[:8]}: {e}")
                return []

            artist_missing = 0
            artist_items: list[HomeAlbum] = []
            for rg in top_releases:
                if artist_missing >= MISSING_ESSENTIALS_MAX_PER_ARTIST:
                    break
                rg_mbid = rg.release_group_mbid
                if not rg_mbid or rg_mbid.lower() in library_album_mbids:
                    continue
                artist_items.append(HomeAlbum(
                    mbid=rg_mbid,
                    name=rg.release_group_name,
                    artist_name=rg.artist_name,
                    listen_count=rg.listen_count,
                    in_library=False,
                ))
                artist_missing += 1

            return artist_items

        artist_results = await asyncio.gather(
            *(_fetch_artist_missing(artist_mbid) for artist_mbid, _ in qualifying_artists[:10]),
            return_exceptions=True,
        )

        all_missing: list[HomeAlbum] = []
        for result in artist_results:
            if isinstance(result, Exception):
                logger.debug("Failed to fetch missing essentials batch item: %s", result)
                continue
            all_missing.extend(result)

        if not all_missing:
            return None

        all_missing.sort(key=lambda x: x.listen_count or 0, reverse=True)
        return HomeSection(
            title="Missing Essentials",
            type="albums",
            items=all_missing[:15],
            source="lidarr",
        )

    def _build_rediscover(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        jf_enabled: bool,
    ) -> HomeSection | None:
        if not jf_enabled:
            return None

        jf_artists = results.get("jf_most_played")
        if not jf_artists:
            return None

        now = datetime.now(timezone.utc)
        rediscover_items: list[HomeArtist] = []
        seen: set[str] = set()

        for item in jf_artists:
            if item.play_count < REDISCOVER_PLAY_THRESHOLD:
                continue
            if not item.last_played:
                continue

            try:
                last_played = datetime.fromisoformat(item.last_played.replace("Z", "+00:00"))
                months_since = (now - last_played).days / 30.0
                if months_since < REDISCOVER_MONTHS_AGO:
                    continue
            except (ValueError, TypeError):
                continue

            artist_name = item.artist_name or item.name
            if artist_name.lower() in seen:
                continue
            seen.add(artist_name.lower())

            mbid = None
            if item.provider_ids:
                mbid = item.provider_ids.get("MusicBrainzArtist")

            image_url = None
            if self._jf_repo and hasattr(self._jf_repo, 'get_image_url'):
                target_id = item.artist_id or item.id
                image_url = prefer_artist_cover_url(
                    mbid,
                    self._jf_repo.get_image_url(target_id, item.image_tag),
                    size=500,
                )

            rediscover_items.append(HomeArtist(
                mbid=mbid,
                name=artist_name,
                listen_count=item.play_count,
                image_url=image_url,
                in_library=mbid.lower() in library_mbids if mbid else False,
            ))

            if len(rediscover_items) >= 15:
                break

        if not rediscover_items:
            return None

        return HomeSection(
            title="Rediscover",
            type="artists",
            items=rediscover_items,
            source="jellyfin",
        )

    def _build_artists_you_might_like(
        self,
        seed_artists: list,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
        resolved_source: str = "listenbrainz",
    ) -> HomeSection | None:
        aggregated: list[HomeArtist] = []
        for i in range(len(seed_artists[:3])):
            similar = results.get(f"similar_{i}")
            if not similar:
                continue
            for artist in similar:
                mbid = getattr(artist, 'artist_mbid', None) or getattr(artist, 'mbid', None)
                name = getattr(artist, 'artist_name', None) or getattr(artist, 'name', '')
                listen_count = getattr(artist, 'listen_count', None) or getattr(artist, 'playcount', 0)
                if not mbid:
                    continue
                if mbid.lower() in seen_artist_mbids:
                    continue
                aggregated.append(HomeArtist(
                    mbid=mbid,
                    name=name,
                    listen_count=listen_count,
                    in_library=mbid.lower() in library_mbids,
                ))
                seen_artist_mbids.add(mbid.lower())

        if not aggregated:
            return None

        aggregated.sort(key=lambda x: x.listen_count or 0, reverse=True)
        source_label = "lastfm" if resolved_source == "lastfm" else "listenbrainz"
        return HomeSection(
            title="Artists You Might Like",
            type="artists",
            items=aggregated[:15],
            source=source_label,
        )

    async def _build_popular_in_genres(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
        resolved_source: str = "listenbrainz",
    ) -> HomeSection | None:
        if resolved_source == "lastfm" and self._lfm_repo:
            return await self._build_popular_in_genres_lastfm(
                results, library_mbids, seen_artist_mbids
            )

        genres = results.get("lb_genres")

        if not genres:
            return None
        else:
            genre_names = []
            for genre in genres[:3]:
                name = genre.genre if hasattr(genre, 'genre') else str(genre)
                genre_names.append(name)

        all_artists: list[HomeArtist] = []
        tag_results = await asyncio.gather(
            *(self._mb_repo.search_artists_by_tag(genre_name, limit=10) for genre_name in genre_names),
            return_exceptions=True,
        )

        for genre_name, tag_artists in zip(genre_names, tag_results):
            if isinstance(tag_artists, Exception):
                logger.debug(f"Failed to search artists for genre '{genre_name}': {tag_artists}")
                continue
            for artist in tag_artists:
                if artist is None:
                    continue
                mbid = artist.musicbrainz_id
                if not mbid or mbid.lower() in seen_artist_mbids:
                    continue
                all_artists.append(HomeArtist(
                    mbid=mbid,
                    name=artist.title if hasattr(artist, 'title') else str(artist),
                    in_library=mbid.lower() in library_mbids,
                ))
                seen_artist_mbids.add(mbid.lower())

        if not all_artists:
            return None

        return HomeSection(
            title="Popular In Your Genres",
            type="artists",
            items=all_artists[:15],
            source="musicbrainz",
        )

    async def _build_popular_in_genres_lastfm(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
    ) -> HomeSection | None:
        top_artists = results.get("lfm_user_top_artists_for_genres") or []
        if not top_artists or not self._lfm_repo:
            return None

        artist_info_results = await asyncio.gather(
            *(
                self._lfm_repo.get_artist_info(artist.name, mbid=artist.mbid)
                for artist in top_artists[:5]
            ),
            return_exceptions=True,
        )

        genre_names: list[str] = []
        seen_genres: set[str] = set()
        for info in artist_info_results:
            if isinstance(info, Exception):
                logger.debug("Failed to get artist info for genre extraction: %s", info)
                continue
            if info and info.tags:
                for tag in info.tags[:2]:
                    if tag.name and tag.name.lower() not in seen_genres:
                        genre_names.append(tag.name)
                        seen_genres.add(tag.name.lower())
                        if len(genre_names) >= 3:
                            break
            if len(genre_names) >= 3:
                break

        if not genre_names:
            return None

        tag_top_artist_results = await asyncio.gather(
            *(
                self._lfm_repo.get_tag_top_artists(genre_name, limit=10)
                for genre_name in genre_names
            ),
            return_exceptions=True,
        )

        all_artists: list[HomeArtist] = []
        for genre_name, tag_artists in zip(genre_names, tag_top_artist_results):
            if isinstance(tag_artists, Exception):
                logger.debug("Failed to get tag top artists for '%s': %s", genre_name, tag_artists)
                continue
            for artist in tag_artists:
                mbid = artist.mbid
                if not mbid or mbid.lower() in seen_artist_mbids:
                    continue
                all_artists.append(HomeArtist(
                    mbid=mbid,
                    name=artist.name,
                    listen_count=artist.playcount,
                    in_library=mbid.lower() in library_mbids,
                ))
                seen_artist_mbids.add(mbid.lower())

        if not all_artists:
            return None

        return HomeSection(
            title="Popular In Your Genres",
            type="artists",
            items=all_artists[:15],
            source="lastfm",
        )

    def _build_genre_list(
        self, results: dict[str, Any], lb_enabled: bool
    ) -> HomeSection | None:
        lb_genres = results.get("lb_genres")
        library_albums = results.get("library_albums") or []
        genres = self._transformers.extract_genres_from_library(library_albums, lb_genres)
        if not genres:
            return None
        source = "listenbrainz" if lb_genres else ("lidarr" if library_albums else None)
        return HomeSection(title="Browse by Genre", type="genres", items=genres, source=source)

    def _build_globally_trending(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
    ) -> HomeSection | None:
        artists = results.get("lb_trending") or []
        items = []
        for artist in artists[:20]:
            home_artist = self._transformers.lb_artist_to_home(artist, library_mbids)
            if home_artist and home_artist.mbid and home_artist.mbid.lower() not in seen_artist_mbids:
                items.append(home_artist)
                seen_artist_mbids.add(home_artist.mbid.lower())

        if not items:
            return None

        return HomeSection(
            title="Globally Trending",
            type="artists",
            items=items[:15],
            source="listenbrainz",
        )

    def _build_lastfm_globally_trending(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
    ) -> HomeSection | None:
        artists = results.get("lfm_global_top") or []
        items = []
        for artist in artists[:20]:
            home_artist = self._transformers.lastfm_artist_to_home(artist, library_mbids)
            if home_artist and home_artist.mbid and home_artist.mbid.lower() not in seen_artist_mbids:
                items.append(home_artist)
                seen_artist_mbids.add(home_artist.mbid.lower())

        if not items:
            return None

        return HomeSection(
            title="Globally Trending",
            type="artists",
            items=items[:15],
            source="lastfm",
        )

    def _build_lastfm_weekly_artist_chart(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
    ) -> HomeSection | None:
        artists = results.get("lfm_weekly_artists") or []
        items = []
        for artist in artists[:20]:
            home_artist = self._transformers.lastfm_artist_to_home(artist, library_mbids)
            if home_artist and home_artist.mbid and home_artist.mbid.lower() not in seen_artist_mbids:
                items.append(home_artist)
                seen_artist_mbids.add(home_artist.mbid.lower())

        if not items:
            return None

        return HomeSection(
            title="Your Weekly Top Artists",
            type="artists",
            items=items[:15],
            source="lastfm",
        )

    async def _build_lastfm_weekly_album_chart(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
    ) -> HomeSection | None:
        albums = results.get("lfm_weekly_albums") or []
        if not albums:
            return None

        release_mbids = list({a.mbid for a in albums[:20] if a.mbid})
        rg_map = await self._resolve_release_mbids(release_mbids) if release_mbids else {}

        items = []
        for album in albums[:20]:
            home_album = self._transformers.lastfm_album_to_home(album, library_mbids)
            if home_album and home_album.mbid:
                home_album.mbid = rg_map.get(home_album.mbid, home_album.mbid)
                items.append(home_album)

        if not items:
            return None

        return HomeSection(
            title="Your Top Albums This Week",
            type="albums",
            items=items[:15],
            source="lastfm",
        )

    async def _build_lastfm_recent_scrobbles(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
    ) -> HomeSection | None:
        tracks = results.get("lfm_recent") or []
        if not tracks:
            return None

        release_mbids = list({t.album_mbid for t in tracks[:30] if t.album_mbid})
        rg_map = await self._resolve_release_mbids(release_mbids) if release_mbids else {}

        items = []
        seen_album_mbids: set[str] = set()
        for track in tracks[:30]:
            home_album = self._transformers.lastfm_recent_to_home(track, library_mbids)
            if home_album and home_album.mbid:
                resolved = rg_map.get(home_album.mbid, home_album.mbid)
                home_album.mbid = resolved
                if resolved.lower() not in seen_album_mbids:
                    items.append(home_album)
                    seen_album_mbids.add(resolved.lower())

        if not items:
            return None

        return HomeSection(
            title="Recently Scrobbled",
            type="albums",
            items=items[:15],
            source="lastfm",
        )

    async def _resolve_release_mbids(self, release_ids: list[str]) -> dict[str, str]:
        if not release_ids:
            return {}
        unique_ids = list(dict.fromkeys(release_ids))
        tasks = [self._mb_repo.get_release_group_id_from_release(rid) for rid in unique_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        rg_map: dict[str, str] = {}
        for rid, rg_id in zip(unique_ids, results):
            if isinstance(rg_id, str) and rg_id:
                rg_map[rid] = rg_id
        return rg_map

    async def _get_genre_artist(self, genre_name: str) -> str | None:
        try:
            artists = await self._mb_repo.search_artists_by_tag(genre_name, limit=10)
            for artist in artists:
                if artist.musicbrainz_id and artist.musicbrainz_id != VARIOUS_ARTISTS_MBID:
                    return artist.musicbrainz_id
        except Exception:
            pass
        return None

    def _build_service_prompts(self) -> list[ServicePrompt]:
        prompts = []
        if not self._is_listenbrainz_enabled():
            prompts.append(ServicePrompt(
                service="listenbrainz",
                title="Connect ListenBrainz",
                description="Get personalized recommendations based on your listening history and discover similar artists. You can also connect Last.fm for global listener stats.",
                icon="🎵",
                color="primary",
                features=["Personalized recommendations", "Similar artists", "Listening stats", "Genre insights"],
            ))
        if not self._is_jellyfin_enabled():
            prompts.append(ServicePrompt(
                service="jellyfin",
                title="Connect Jellyfin",
                description="Rediscover forgotten favorites and get recommendations based on your play history.",
                icon="📺",
                color="secondary",
                features=["Rediscover favorites", "Play statistics", "Listening history", "Better recommendations"],
            ))
        if not self._is_lidarr_configured():
            prompts.append(ServicePrompt(
                service="lidarr-connection",
                title="Connect Lidarr",
                description="Find missing essentials in your collection and manage your music library.",
                icon="🎶",
                color="accent",
                features=["Missing essentials", "Library management", "Album requests", "Collection tracking"],
            ))
        if not self._is_lastfm_enabled():
            prompts.append(ServicePrompt(
                service="lastfm",
                title="Connect Last.fm",
                description="Scrobble your plays, see global listener stats, and get recommendations powered by Last.fm's music data.",
                icon="🎸",
                color="primary",
                features=["Scrobbling", "Global listener stats", "Artist recommendations", "Play history"],
            ))
        return prompts

    async def _execute_tasks(self, tasks: dict[str, Any]) -> dict[str, Any]:
        if not tasks:
            return {}
        keys = list(tasks.keys())
        coros = list(tasks.values())
        raw_results = await asyncio.gather(*coros, return_exceptions=True)
        results = {}
        for key, result in zip(keys, raw_results):
            if isinstance(result, Exception):
                logger.warning(f"Discover task {key} failed: {result}")
                results[key] = None
            else:
                results[key] = result
        return results

    # ── Discover Queue ──────────────────────────────────────────────

    async def build_queue(self, count: int | None = None, source: str | None = None) -> DiscoverQueueResponse:
        qs = self._get_queue_settings()
        if count is None:
            count = qs.queue_size
        resolved_source = self.resolve_source(source)
        logger.info("Building discover queue: requested_source=%s, resolved_source=%s", source, resolved_source)
        lb_enabled = self._is_listenbrainz_enabled()
        jf_enabled = self._is_jellyfin_enabled()
        lidarr_configured = self._is_lidarr_configured()
        lfm_enabled = self._is_lastfm_enabled()
        username = self._get_listenbrainz_username()
        lfm_username = self._get_lastfm_username()

        if lb_enabled and username:
            lb_settings = self._preferences.get_listenbrainz_connection()
            self._lb_repo.configure(username=username, user_token=lb_settings.user_token)
        if jf_enabled:
            jf_settings = self._preferences.get_jellyfin_connection()
            self._jf_repo.configure(
                base_url=jf_settings.jellyfin_url,
                api_key=jf_settings.api_key,
                user_id=jf_settings.user_id,
            )

        ignored_mbids = set()
        if self._library_cache:
            try:
                ignored_mbids = await self._library_cache.get_ignored_release_mbids()
            except Exception:
                pass

        library_album_mbids = await self._get_library_album_mbids(lidarr_configured)
        listened_release_group_mbids = await self._get_user_listened_release_group_mbids(
            lb_enabled,
            username,
            resolved_source,
        )

        has_services = lb_enabled or jf_enabled or (lfm_enabled and lfm_username)
        if has_services:
            items = await self._build_personalized_queue(
                count, lb_enabled, username, jf_enabled, ignored_mbids, library_album_mbids,
                listened_release_group_mbids,
                resolved_source=resolved_source,
                lfm_enabled=lfm_enabled,
                lfm_username=lfm_username,
            )
        else:
            items = await self._build_anonymous_queue(
                count, ignored_mbids, library_album_mbids, resolved_source=resolved_source
            )

        return DiscoverQueueResponse(
            items=items,
            queue_id=str(uuid.uuid4()),
        )

    async def _get_library_album_mbids(self, lidarr_configured: bool) -> set[str]:
        if not lidarr_configured:
            if self._library_cache:
                try:
                    return await self._library_cache.get_all_album_mbids()
                except Exception:
                    pass
            return set()
        try:
            return await self._lidarr_repo.get_library_mbids(include_release_ids=False)
        except Exception:
            return set()

    async def _get_user_listened_release_group_mbids(
        self,
        lb_enabled: bool,
        username: str | None,
        resolved_source: str,
    ) -> set[str]:
        if resolved_source != "listenbrainz" or not lb_enabled or not username:
            return set()

        try:
            listened = await self._lb_repo.get_user_top_release_groups(
                username=username,
                range_="all_time",
                count=100,
            )
        except Exception:
            return set()

        return {
            rg.release_group_mbid.lower()
            for rg in listened
            if getattr(rg, "release_group_mbid", None)
        }

    def _make_queue_item(
        self,
        *,
        release_group_mbid: str,
        album_name: str,
        artist_name: str,
        artist_mbid: str,
        reason: str,
        is_wildcard: bool = False,
    ) -> DiscoverQueueItemLight:
        return DiscoverQueueItemLight(
            release_group_mbid=release_group_mbid,
            album_name=album_name,
            artist_name=artist_name,
            artist_mbid=artist_mbid,
            cover_url=f"/api/covers/release-group/{release_group_mbid}?size=500",
            recommendation_reason=reason,
            is_wildcard=is_wildcard,
            in_library=False,
        )

    async def _build_lb_similar_seed_pools(
        self,
        seeds: list[ListenBrainzArtist],
        excluded_mbids: set[str],
        qs: QueueSettings,
    ) -> list[list[DiscoverQueueItemLight]]:
        pools: list[list[DiscoverQueueItemLight]] = [[] for _ in range(len(seeds))]

        async def _process_seed(i: int, seed: ListenBrainzArtist) -> None:
            seed_mbid = seed.artist_mbids[0] if seed.artist_mbids else None
            if not seed_mbid:
                return

            pool_seen: set[str] = set()
            try:
                similar = await self._lb_repo.get_similar_artists(
                    seed_mbid,
                    max_similar=qs.similar_artists_limit,
                )
                for sim_artist in similar:
                    sim_mbid = self._normalize_mbid(sim_artist.artist_mbid)
                    if not sim_mbid or sim_mbid == VARIOUS_ARTISTS_MBID:
                        continue

                    try:
                        release_groups = await self._lb_repo.get_artist_top_release_groups(
                            sim_mbid,
                            count=qs.albums_per_similar,
                        )
                    except Exception as e:
                        logger.debug(f"Failed to get releases for similar artist: {e}")
                        continue

                    for rg in release_groups:
                        rg_mbid = self._normalize_mbid(rg.release_group_mbid)
                        if not rg_mbid:
                            continue
                        if rg_mbid in excluded_mbids or rg_mbid in pool_seen:
                            continue
                        pools[i].append(
                            self._make_queue_item(
                                release_group_mbid=rg_mbid,
                                album_name=rg.release_group_name,
                                artist_name=rg.artist_name,
                                artist_mbid=sim_mbid,
                                reason=f"Similar to {seed.artist_name}",
                            )
                        )
                        pool_seen.add(rg_mbid)
            except Exception as e:
                logger.debug(f"Failed to get similar artists for seed {seed_mbid[:8]}: {e}")

        await asyncio.gather(*[_process_seed(i, seed) for i, seed in enumerate(seeds)])
        return pools

    async def _strategy_lb_genre_discovery(
        self,
        username: str,
        excluded_mbids: set[str],
    ) -> list[DiscoverQueueItemLight]:
        try:
            genres = await self._lb_repo.get_user_genre_activity(username)
        except Exception:
            return []

        if not genres:
            return []

        top_genres = [genre.genre for genre in genres[:4] if getattr(genre, "genre", None)]
        if not top_genres:
            return []

        search_results = await asyncio.gather(
            *[
                self._mb_repo.search_release_groups_by_tag(tag=genre, limit=8)
                for genre in top_genres
            ],
            return_exceptions=True,
        )

        items: list[DiscoverQueueItemLight] = []
        seen: set[str] = set()
        for genre, result in zip(top_genres, search_results):
            if isinstance(result, Exception):
                continue
            for release in result:
                rg_mbid = self._normalize_mbid(getattr(release, "musicbrainz_id", None))
                if not rg_mbid:
                    continue
                if rg_mbid in excluded_mbids or rg_mbid in seen:
                    continue
                items.append(
                    self._make_queue_item(
                        release_group_mbid=rg_mbid,
                        album_name=getattr(release, "title", "Unknown"),
                        artist_name=getattr(release, "artist", "Unknown") or "Unknown",
                        artist_mbid="",
                        reason=f"Because you listen to {genre}",
                    )
                )
                seen.add(rg_mbid)
        return items

    async def _strategy_lb_fresh_releases(
        self,
        username: str,
        excluded_mbids: set[str],
    ) -> list[DiscoverQueueItemLight]:
        try:
            fresh_releases = await self._lb_repo.get_user_fresh_releases(username)
        except Exception:
            return []

        if not fresh_releases:
            return []

        items: list[DiscoverQueueItemLight] = []
        seen: set[str] = set()
        for release in fresh_releases:
            if not isinstance(release, dict):
                continue
            rg_mbid = self._normalize_mbid(release.get("release_group_mbid"))
            if not rg_mbid:
                continue
            if rg_mbid in excluded_mbids or rg_mbid in seen:
                continue

            artist_mbids = release.get("artist_mbids")
            first_artist_mbid = ""
            if isinstance(artist_mbids, list) and artist_mbids:
                first_artist_mbid = self._normalize_mbid(artist_mbids[0]) or ""

            album_name = release.get("title") or release.get("release_group_name") or "Unknown"
            artist_name = release.get("artist_credit_name") or release.get("artist_name") or "Unknown"
            items.append(
                self._make_queue_item(
                    release_group_mbid=rg_mbid,
                    album_name=album_name,
                    artist_name=artist_name,
                    artist_mbid=first_artist_mbid,
                    reason="New release for you",
                )
            )
            seen.add(rg_mbid)
        return items

    async def _strategy_lb_loved_artists(
        self,
        username: str,
        excluded_mbids: set[str],
        albums_per_artist: int,
    ) -> list[DiscoverQueueItemLight]:
        try:
            loved = await self._lb_repo.get_user_loved_recordings(
                username=username,
                count=50,
            )
        except Exception:
            return []

        artist_mbids: list[str] = []
        seen_artists: set[str] = set()
        for recording in loved:
            mbids = getattr(recording, "artist_mbids", None) or []
            if not mbids:
                continue
            normalized = self._normalize_mbid(mbids[0])
            if not normalized or normalized in seen_artists:
                continue
            artist_mbids.append(normalized)
            seen_artists.add(normalized)
            if len(artist_mbids) >= 6:
                break

        if not artist_mbids:
            return []

        results = await asyncio.gather(
            *[
                self._lb_repo.get_artist_top_release_groups(artist_mbid, count=albums_per_artist)
                for artist_mbid in artist_mbids
            ],
            return_exceptions=True,
        )

        items: list[DiscoverQueueItemLight] = []
        seen_rg_mbids: set[str] = set()
        for artist_mbid, result in zip(artist_mbids, results):
            if isinstance(result, Exception):
                continue
            for rg in result:
                rg_mbid = self._normalize_mbid(rg.release_group_mbid)
                if not rg_mbid:
                    continue
                if rg_mbid in excluded_mbids or rg_mbid in seen_rg_mbids:
                    continue
                items.append(
                    self._make_queue_item(
                        release_group_mbid=rg_mbid,
                        album_name=rg.release_group_name,
                        artist_name=rg.artist_name,
                        artist_mbid=artist_mbid,
                        reason="From an artist you love",
                    )
                )
                seen_rg_mbids.add(rg_mbid)
        return items

    async def _strategy_lb_top_artist_deep_cuts(
        self,
        username: str,
        excluded_mbids: set[str],
        listened_mbids: set[str],
        albums_per_artist: int,
    ) -> list[DiscoverQueueItemLight]:
        try:
            top_release_groups = await self._lb_repo.get_user_top_release_groups(
                username=username,
                range_="this_month",
                count=25,
            )
        except Exception:
            return []

        if not top_release_groups:
            return []

        current_top_mbids = {
            rg.release_group_mbid.lower()
            for rg in top_release_groups
            if getattr(rg, "release_group_mbid", None)
        }

        artist_seed_names: dict[str, str] = {}
        for rg in top_release_groups:
            artist_mbids = getattr(rg, "artist_mbids", None) or []
            if not artist_mbids:
                continue
            artist_mbid = self._normalize_mbid(artist_mbids[0])
            if not artist_mbid or artist_mbid in artist_seed_names:
                continue
            artist_seed_names[artist_mbid] = getattr(rg, "artist_name", "")
            if len(artist_seed_names) >= 6:
                break

        if not artist_seed_names:
            return []

        artist_mbids = list(artist_seed_names.keys())
        results = await asyncio.gather(
            *[
                self._lb_repo.get_artist_top_release_groups(
                    artist_mbid,
                    count=max(albums_per_artist + 2, 4),
                )
                for artist_mbid in artist_mbids
            ],
            return_exceptions=True,
        )

        items: list[DiscoverQueueItemLight] = []
        seen_rg_mbids: set[str] = set()
        for artist_mbid, result in zip(artist_mbids, results):
            if isinstance(result, Exception):
                continue
            for rg in result:
                rg_mbid = self._normalize_mbid(rg.release_group_mbid)
                if not rg_mbid:
                    continue
                if rg_mbid in current_top_mbids or rg_mbid in listened_mbids:
                    continue
                if rg_mbid in excluded_mbids or rg_mbid in seen_rg_mbids:
                    continue

                source_artist_name = artist_seed_names.get(artist_mbid) or rg.artist_name
                items.append(
                    self._make_queue_item(
                        release_group_mbid=rg_mbid,
                        album_name=rg.release_group_name,
                        artist_name=rg.artist_name,
                        artist_mbid=artist_mbid,
                        reason=f"More from {source_artist_name}",
                    )
                )
                seen_rg_mbids.add(rg_mbid)
        return items

    async def _build_personalized_queue(
        self,
        count: int,
        lb_enabled: bool,
        username: str | None,
        jf_enabled: bool,
        ignored_mbids: set[str],
        library_album_mbids: set[str],
        listened_release_group_mbids: set[str],
        resolved_source: str = "listenbrainz",
        lfm_enabled: bool = False,
        lfm_username: str | None = None,
    ) -> list[DiscoverQueueItemLight]:
        seed_artists = await self._get_seed_artists(
            lb_enabled, username, jf_enabled,
            resolved_source=resolved_source,
            lfm_enabled=lfm_enabled,
            lfm_username=lfm_username,
        )
        if not seed_artists:
            return await self._build_anonymous_queue(
                count, ignored_mbids, library_album_mbids, resolved_source=resolved_source
            )

        qs = self._get_queue_settings()
        use_lastfm = resolved_source == "lastfm" and lfm_enabled and self._lfm_repo is not None
        seeds = seed_artists[:qs.seed_artists]
        wildcard_slots = qs.wildcard_slots
        personalized_target = max(count - wildcard_slots, 0)
        seed_target = max(4, (personalized_target // max(len(seeds), 1)) + 3)
        excluded_mbids = ignored_mbids | library_album_mbids
        mbid_resolution_cache: dict[str, str | None] = {}

        candidate_pools: list[list[DiscoverQueueItemLight]] = []
        if use_lastfm:
            candidate_pools = [[] for _ in range(len(seeds))]

            async def _process_seed_lastfm(i: int, seed: Any) -> None:
                seed_mbid = seed.artist_mbids[0] if seed.artist_mbids else None
                if not seed_mbid:
                    return
                try:
                    similar_raw = await self._lfm_repo.get_similar_artists(
                        seed.artist_name,
                        mbid=seed_mbid,
                        limit=qs.similar_artists_limit,
                    )
                    valid_sims = [
                        sim
                        for sim in similar_raw
                        if self._normalize_mbid(sim.mbid)
                        and self._normalize_mbid(sim.mbid) != VARIOUS_ARTISTS_MBID
                    ]
                    album_fetch_results = await asyncio.gather(
                        *[
                            self._lfm_repo.get_artist_top_albums(
                                sim.name,
                                mbid=sim.mbid,
                                limit=qs.albums_per_similar,
                            )
                            for sim in valid_sims
                        ],
                        return_exceptions=True,
                    )
                    sim_albums_map: list[tuple[Any, list]] = []
                    for sim, result in zip(valid_sims, album_fetch_results):
                        if isinstance(result, Exception):
                            logger.debug("Failed to get Last.fm albums for %s: %s", sim.name, result)
                            continue
                        sim_albums_map.append((sim, result))
                    candidate_pools[i] = await self._lastfm_albums_to_queue_items(
                        sim_albums_map,
                        exclude=excluded_mbids,
                        target=seed_target,
                        reason=f"Similar to {seed.artist_name}",
                        resolver_cache=mbid_resolution_cache,
                        use_album_artist_name=False,
                    )
                except Exception as e:
                    logger.debug(f"Failed to get similar artists for seed {seed_mbid[:8]}: {e}")

            await asyncio.gather(*[_process_seed_lastfm(i, seed) for i, seed in enumerate(seeds)])
        else:
            deep_cut_excluded = excluded_mbids | listened_release_group_mbids
            strategy_names = [
                "similar_seeds", "genre_discovery", "fresh_releases",
                "loved_artists", "deep_cuts",
            ]
            strategy_results = await asyncio.gather(
                self._build_lb_similar_seed_pools(seeds, excluded_mbids, qs),
                self._strategy_lb_genre_discovery(username or "", excluded_mbids),
                self._strategy_lb_fresh_releases(username or "", excluded_mbids),
                self._strategy_lb_loved_artists(
                    username or "",
                    excluded_mbids,
                    qs.albums_per_similar,
                ),
                self._strategy_lb_top_artist_deep_cuts(
                    username or "",
                    deep_cut_excluded,
                    listened_release_group_mbids,
                    qs.albums_per_similar,
                ),
                return_exceptions=True,
            )

            similar_seed_pools = strategy_results[0]
            if isinstance(similar_seed_pools, list):
                candidate_pools.extend(similar_seed_pools)
                pool_counts = [len(p) for p in similar_seed_pools]
                logger.info("Strategy similar_seeds: %d pools, items per pool: %s", len(similar_seed_pools), pool_counts)
            elif isinstance(similar_seed_pools, Exception):
                logger.warning("Strategy similar_seeds FAILED: %s", similar_seed_pools)

            for idx, strategy_result in enumerate(strategy_results[1:], start=1):
                name = strategy_names[idx]
                if isinstance(strategy_result, Exception):
                    logger.warning("Strategy %s FAILED: %s", name, strategy_result)
                    continue
                if strategy_result:
                    candidate_pools.append(strategy_result)
                    logger.info("Strategy %s: %d items", name, len(strategy_result))
                else:
                    logger.info("Strategy %s: 0 items", name)

        personalized = self._round_robin_select(candidate_pools, personalized_target)
        logger.info(
            "Personalized queue: %d items from %d pools (target=%d, wildcard_slots=%d)",
            len(personalized), len(candidate_pools), personalized_target, wildcard_slots,
        )
        seen_mbids = {item.release_group_mbid.lower() for item in personalized}

        wildcard_count = max(wildcard_slots, count - len(personalized))
        wildcards = await self._get_wildcard_albums(
            wildcard_count, ignored_mbids, library_album_mbids, seen_mbids,
            resolved_source=resolved_source,
        )
        queue_items = self._interleave_wildcards(personalized, wildcards)

        if len(queue_items) < count:
            top_up_seen = {item.release_group_mbid.lower() for item in queue_items}
            top_up = await self._get_wildcard_albums(
                count - len(queue_items),
                ignored_mbids,
                library_album_mbids,
                top_up_seen,
                resolved_source=resolved_source,
            )
            queue_items.extend(top_up)

        return queue_items[:count]

    def _round_robin_select(
        self, pools: list[list[DiscoverQueueItemLight]], count: int
    ) -> list[DiscoverQueueItemLight]:
        selected: list[DiscoverQueueItemLight] = []
        seen_mbids: set[str] = set()
        artist_counts: dict[str, int] = {}
        max_per_artist = 2

        for pool in pools:
            random.shuffle(pool)

        pool_indices = [0] * len(pools)

        for _ in range(count * 3):
            if len(selected) >= count:
                break
            for pool_idx in range(len(pools)):
                if len(selected) >= count:
                    break
                pool = pools[pool_idx]
                idx = pool_indices[pool_idx]
                while idx < len(pool):
                    item = pool[idx]
                    idx += 1
                    pool_indices[pool_idx] = idx
                    mbid_lower = item.release_group_mbid.lower()
                    artist_key = item.artist_mbid.lower() if item.artist_mbid else ""
                    if mbid_lower in seen_mbids:
                        continue
                    if artist_key and artist_counts.get(artist_key, 0) >= max_per_artist:
                        continue
                    selected.append(item)
                    seen_mbids.add(mbid_lower)
                    if artist_key:
                        artist_counts[artist_key] = artist_counts.get(artist_key, 0) + 1
                    break

        return selected

    async def _get_wildcard_albums(
        self, count: int, ignored_mbids: set[str], library_album_mbids: set[str],
        seen_mbids: set[str] | None = None,
        resolved_source: str = "listenbrainz",
    ) -> list[DiscoverQueueItemLight]:
        if count <= 0:
            return []
        exclude = ignored_mbids | library_album_mbids | (seen_mbids or set())
        use_lastfm = resolved_source == "lastfm" and self._is_lastfm_enabled() and self._lfm_repo is not None
        target = max(count * 2, 6)

        try:
            if use_lastfm:
                top_artists = await self._lfm_repo.get_global_top_artists(limit=15)
                random.shuffle(top_artists)
                valid_artists = [
                    a
                    for a in top_artists[:10]
                    if self._normalize_mbid(a.mbid) != VARIOUS_ARTISTS_MBID
                ]
                album_fetch_results = await asyncio.gather(
                    *[
                        self._lfm_repo.get_artist_top_albums(
                            a.name, mbid=a.mbid, limit=3
                        )
                        for a in valid_artists
                    ],
                    return_exceptions=True,
                )
                artist_albums_pairs: list[tuple[Any, list]] = []
                for artist, result in zip(valid_artists, album_fetch_results):
                    if isinstance(result, Exception):
                        continue
                    artist_albums_pairs.append((artist, result))
                wildcards = await self._lastfm_albums_to_queue_items(
                    artist_albums_pairs,
                    exclude=exclude,
                    target=target,
                    reason="Trending on Last.fm",
                    is_wildcard=True,
                )
            else:
                rgs = await self._lb_repo.get_sitewide_top_release_groups(count=25)
                random.shuffle(rgs)
                wildcards: list[DiscoverQueueItemLight] = []
                for rg in rgs:
                    if len(wildcards) >= target:
                        break
                    rg_mbid = rg.release_group_mbid
                    if not rg_mbid or rg_mbid.lower() in exclude:
                        continue
                    artist_mbid = rg.artist_mbids[0] if rg.artist_mbids else ""
                    if artist_mbid.lower() == VARIOUS_ARTISTS_MBID:
                        continue
                    wildcards.append(DiscoverQueueItemLight(
                        release_group_mbid=rg_mbid,
                        album_name=rg.release_group_name,
                        artist_name=rg.artist_name,
                        artist_mbid=artist_mbid,
                        cover_url=f"/api/covers/release-group/{rg_mbid}?size=500",
                        recommendation_reason="Trending This Week",
                        is_wildcard=True,
                        in_library=False,
                    ))
        except Exception as e:
            logger.debug(f"Failed to get wildcard albums: {e}")
            wildcards = []

        if not wildcards:
            if use_lastfm:
                decade_tags = ["2020s", "2010s", "2000s", "1990s", "1980s", "1970s"]
                for decade in decade_tags:
                    if len(wildcards) >= target:
                        break
                    try:
                        decade_releases = await self._mb_repo.search_release_groups_by_tag(
                            tag=decade,
                            limit=25,
                            offset=0,
                        )
                    except Exception:
                        continue
                    for release in decade_releases:
                        if len(wildcards) >= target:
                            break
                        rg_mbid = self._normalize_mbid(getattr(release, "musicbrainz_id", None))
                        if not rg_mbid or rg_mbid.lower() in exclude:
                            continue
                        wildcards.append(DiscoverQueueItemLight(
                            release_group_mbid=rg_mbid,
                            album_name=getattr(release, "title", "Unknown"),
                            artist_name=getattr(release, "artist", "Unknown") or "Unknown",
                            artist_mbid="",
                            cover_url=f"/api/covers/release-group/{rg_mbid}?size=500",
                            recommendation_reason="Trending on Last.fm",
                            is_wildcard=True,
                            in_library=False,
                        ))
                        exclude.add(rg_mbid.lower())

        if not wildcards:
            logger.warning("Failed to populate any wildcard albums for discover queue")

        return wildcards[:count]

    def _interleave_wildcards(
        self,
        personalized: list[DiscoverQueueItemLight],
        wildcards: list[DiscoverQueueItemLight],
    ) -> list[DiscoverQueueItemLight]:
        result = list(personalized)
        positions = [2, 7]
        for i, wc in enumerate(wildcards):
            pos = positions[i] if i < len(positions) else len(result)
            pos = min(pos, len(result))
            result.insert(pos, wc)
        return result

    async def _build_anonymous_queue(
        self, count: int, ignored_mbids: set[str], library_album_mbids: set[str],
        resolved_source: str = "listenbrainz",
    ) -> list[DiscoverQueueItemLight]:
        items: list[DiscoverQueueItemLight] = []
        use_lastfm = resolved_source == "lastfm" and self._is_lastfm_enabled() and self._lfm_repo is not None
        exclude = ignored_mbids | library_album_mbids

        try:
            if use_lastfm:
                top_artists = await self._lfm_repo.get_global_top_artists(limit=15)
                random.shuffle(top_artists)
                valid_artists = [
                    a
                    for a in top_artists
                    if self._normalize_mbid(a.mbid) != VARIOUS_ARTISTS_MBID
                ]
                album_fetch_results = await asyncio.gather(
                    *[
                        self._lfm_repo.get_artist_top_albums(
                            a.name, mbid=a.mbid, limit=3
                        )
                        for a in valid_artists
                    ],
                    return_exceptions=True,
                )
                artist_albums_pairs: list[tuple[Any, list]] = []
                for artist, result in zip(valid_artists, album_fetch_results):
                    if isinstance(result, Exception):
                        continue
                    artist_albums_pairs.append((artist, result))
                items = await self._lastfm_albums_to_queue_items(
                    artist_albums_pairs,
                    exclude=exclude,
                    target=count,
                    reason="Trending on Last.fm",
                    is_wildcard=True,
                )
            else:
                trending = await self._lb_repo.get_sitewide_top_release_groups(count=50)
                random.shuffle(trending)
                for rg in trending:
                    if len(items) >= count:
                        break
                    rg_mbid = rg.release_group_mbid
                    if not rg_mbid or rg_mbid.lower() in exclude:
                        continue
                    artist_mbid = rg.artist_mbids[0] if rg.artist_mbids else ""
                    if artist_mbid.lower() == VARIOUS_ARTISTS_MBID:
                        continue
                    items.append(DiscoverQueueItemLight(
                        release_group_mbid=rg_mbid,
                        album_name=rg.release_group_name,
                        artist_name=rg.artist_name,
                        artist_mbid=artist_mbid,
                        cover_url=f"/api/covers/release-group/{rg_mbid}?size=500",
                        recommendation_reason="Trending This Week",
                        is_wildcard=True,
                        in_library=False,
                    ))
        except Exception as e:
            logger.debug(f"Failed to get trending for anonymous queue: {e}")

        if len(items) < count:
            top_up_seen = {item.release_group_mbid.lower() for item in items}
            top_up = await self._get_wildcard_albums(
                count - len(items),
                ignored_mbids,
                library_album_mbids,
                top_up_seen,
                resolved_source=resolved_source,
            )
            items.extend(top_up)

        return items[:count]

    async def enrich_queue_item(self, release_group_mbid: str) -> DiscoverQueueEnrichment:
        cache_key = f"discover_queue_enrich:{release_group_mbid}"
        if self._memory_cache:
            cached = await self._memory_cache.get(cache_key)
            if cached is not None and isinstance(cached, DiscoverQueueEnrichment):
                return cached

        if release_group_mbid in self._enrich_in_flight:
            return await self._enrich_in_flight[release_group_mbid]

        loop = asyncio.get_running_loop()
        future: asyncio.Future[DiscoverQueueEnrichment] = loop.create_future()
        self._enrich_in_flight[release_group_mbid] = future
        try:
            result = await self._do_enrich_queue_item(release_group_mbid, cache_key)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._enrich_in_flight.pop(release_group_mbid, None)

    async def _do_enrich_queue_item(
        self, release_group_mbid: str, cache_key: str
    ) -> DiscoverQueueEnrichment:

        enrichment = DiscoverQueueEnrichment()

        rg_data = await self._mb_repo.get_release_group_by_id(
            release_group_mbid,
            includes=["artist-credits", "releases", "tags", "url-rels"],
        )

        artist_mbid = ""
        youtube_url = None

        if rg_data:
            tags_raw = rg_data.get("tags", [])
            enrichment.tags = [t.get("name", "") for t in tags_raw if t.get("name")][:10]

            youtube_raw = self._mb_repo.extract_youtube_url_from_relations(rg_data)
            if youtube_raw:
                youtube_url = self._mb_repo.youtube_url_to_embed(youtube_raw)

            ac_list = rg_data.get("artist-credit", [])
            for ac in ac_list:
                a = ac.get("artist", {}) if isinstance(ac, dict) else {}
                if a.get("id"):
                    artist_mbid = a["id"]
                    break
            enrichment.artist_mbid = artist_mbid or None

            releases = rg_data.get("releases") or rg_data.get("release-list", [])
            if releases:
                first_release = releases[0]
                enrichment.release_date = first_release.get("date")

                if not youtube_url:
                    release_data = await self._mb_repo.get_release_by_id(
                        first_release["id"],
                        includes=["recordings", "url-rels"],
                    )
                    if release_data:
                        yt_raw = self._mb_repo.extract_youtube_url_from_relations(release_data)
                        if yt_raw:
                            youtube_url = self._mb_repo.youtube_url_to_embed(yt_raw)

                        if not youtube_url:
                            tracks = release_data.get("media") or release_data.get("medium-list", [])
                            rec_ids: list[str] = []
                            for medium in tracks:
                                for track in medium.get("tracks") or medium.get("track-list", []):
                                    rec_id = track.get("recording", {}).get("id")
                                    if rec_id:
                                        rec_ids.append(rec_id)
                                    if len(rec_ids) >= 3:
                                        break
                                if len(rec_ids) >= 3:
                                    break
                            if rec_ids:
                                rec_results = await asyncio.gather(
                                    *[
                                        self._mb_repo.get_recording_by_id(rid, includes=["url-rels"])
                                        for rid in rec_ids
                                    ],
                                    return_exceptions=True,
                                )
                                for rec_data in rec_results:
                                    if isinstance(rec_data, Exception) or not rec_data:
                                        continue
                                    yt_raw = self._mb_repo.extract_youtube_url_from_relations(rec_data)
                                    if yt_raw:
                                        youtube_url = self._mb_repo.youtube_url_to_embed(yt_raw)
                                        break

        enrichment.youtube_url = youtube_url

        if not youtube_url:
            yt_settings = self._preferences.get_youtube_connection()
            enrichment.youtube_search_available = yt_settings.enabled and bool(yt_settings.api_key)

        album_name = rg_data.get("title", "") if rg_data else ""
        artist_name_for_search = ""
        if rg_data:
            ac_list = rg_data.get("artist-credit", [])
            for ac in ac_list:
                a = ac.get("artist", {}) if isinstance(ac, dict) else {}
                if a.get("name"):
                    artist_name_for_search = a["name"]
                    break
        enrichment.youtube_search_url = (
            f"https://www.youtube.com/results?search_query={quote_plus(f'{artist_name_for_search} {album_name}')}"
        )

        parallel_tasks: dict[str, Any] = {}

        async def _get_artist_and_bio():
            if not artist_mbid:
                return
            try:
                mb_artist = await self._mb_repo.get_artist_by_id(artist_mbid)
                if mb_artist:
                    enrichment.country = mb_artist.get("country") or mb_artist.get("area", {}).get("name", "")
                    if self._wikidata_repo:
                        url_rels = mb_artist.get("relations", [])
                        wiki_url = None
                        for rel in url_rels:
                            if rel.get("type") in ("wikipedia", "wikidata"):
                                url_obj = rel.get("url", {})
                                wiki_url = url_obj.get("resource", "") if isinstance(url_obj, dict) else ""
                                break
                        if wiki_url:
                            bio = await self._wikidata_repo.get_wikipedia_extract(wiki_url)
                            if bio:
                                enrichment.artist_description = bio
            except Exception as e:
                logger.debug(f"Failed to get artist MB data: {e}")

        async def _get_listen_count():
            try:
                counts = await self._lb_repo.get_release_group_popularity_batch(
                    [release_group_mbid]
                )
                if counts:
                    enrichment.listen_count = counts.get(release_group_mbid)
            except Exception as e:
                logger.debug(f"Failed to get listen count: {e}")

        async def _apply_lastfm_fallback():
            if not self._lfm_repo or not self._is_lastfm_enabled():
                return
            if not album_name or not artist_name_for_search:
                return

            try:
                album_info = await self._lfm_repo.get_album_info(
                    artist=artist_name_for_search,
                    album=album_name,
                )
                if album_info:
                    if not enrichment.tags and album_info.tags:
                        enrichment.tags = [tag.name for tag in album_info.tags if tag.name][:10]
                    if not enrichment.artist_description and album_info.summary:
                        cleaned_summary = clean_lastfm_bio(album_info.summary)
                        if cleaned_summary:
                            enrichment.artist_description = cleaned_summary
            except Exception as e:
                logger.debug("Failed Last.fm album fallback for discover queue: %s", e)

            if enrichment.artist_description and enrichment.tags:
                return

            try:
                artist_info = await self._lfm_repo.get_artist_info(
                    artist=artist_name_for_search,
                    mbid=artist_mbid or None,
                )
                if not artist_info:
                    return
                if not enrichment.artist_mbid and artist_info.mbid:
                    enrichment.artist_mbid = artist_info.mbid
                if not enrichment.tags and artist_info.tags:
                    enrichment.tags = [tag.name for tag in artist_info.tags if tag.name][:10]
                if not enrichment.artist_description and artist_info.bio_summary:
                    cleaned_bio = clean_lastfm_bio(artist_info.bio_summary)
                    if cleaned_bio:
                        enrichment.artist_description = cleaned_bio
            except Exception as e:
                logger.debug("Failed Last.fm artist fallback for discover queue: %s", e)

        await asyncio.gather(_get_artist_and_bio(), _get_listen_count(), _apply_lastfm_fallback())

        if self._memory_cache:
            enrich_ttl = self._get_queue_settings().enrich_ttl
            await self._memory_cache.set(cache_key, enrichment, enrich_ttl)

        return enrichment

    async def validate_queue_mbids(self, mbids: list[str]) -> list[str]:
        library_mbids: set[str] = set()
        if self._library_cache:
            try:
                library_mbids = await self._library_cache.get_all_album_mbids()
            except Exception:
                pass
        if not library_mbids:
            try:
                lidarr_configured = self._is_lidarr_configured()
                if lidarr_configured:
                    library_mbids = await self._get_library_album_mbids(True)
            except Exception:
                pass
        lowered_library = {lm.lower() for lm in library_mbids}
        return [m for m in mbids if m.lower() in lowered_library]

    async def ignore_release(
        self, release_group_mbid: str, artist_mbid: str, release_name: str, artist_name: str
    ) -> None:
        if self._library_cache:
            await self._library_cache.add_ignored_release(
                release_group_mbid, artist_mbid, release_name, artist_name
            )

    async def get_ignored_releases(self) -> list[DiscoverIgnoredRelease]:
        if self._library_cache:
            rows = await self._library_cache.get_ignored_releases()
            return [DiscoverIgnoredRelease(**row) for row in rows]
        return []

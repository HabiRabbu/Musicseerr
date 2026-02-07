import asyncio
import logging
import random
import re
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
)
from services.preferences_service import PreferencesService
from services.home_transformers import HomeDataTransformers
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.persistent_cache import LibraryCache
from repositories.listenbrainz_models import ListenBrainzArtist

logger = logging.getLogger(__name__)

DISCOVER_CACHE_KEY = "discover_response"
DISCOVER_CACHE_TTL = 43200  # 12 hours
DISCOVER_QUEUE_ENRICH_TTL = 86400  # 24 hours
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
    ):
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._preferences = preferences_service
        self._memory_cache = memory_cache
        self._library_cache = library_cache
        self._wikidata_repo = wikidata_repo
        self._transformers = HomeDataTransformers(jellyfin_repo)
        self._building = False

    def _is_listenbrainz_enabled(self) -> bool:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.enabled and bool(lb_settings.username)

    def _is_jellyfin_enabled(self) -> bool:
        jf_settings = self._preferences.get_jellyfin_connection()
        return jf_settings.enabled and bool(jf_settings.jellyfin_url) and bool(jf_settings.api_key)

    def _is_lidarr_configured(self) -> bool:
        lidarr_connection = self._preferences.get_lidarr_connection()
        return bool(lidarr_connection.lidarr_url) and bool(lidarr_connection.lidarr_api_key)

    def _get_listenbrainz_username(self) -> str | None:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.username if lb_settings.enabled else None

    async def get_discover_data(self) -> DiscoverResponse:
        if self._memory_cache:
            cached = await self._memory_cache.get(DISCOVER_CACHE_KEY)
            if cached is not None:
                if isinstance(cached, DiscoverResponse):
                    return cached.model_copy(update={"refreshing": self._building})
        if not self._building:
            asyncio.create_task(self.warm_cache())
        return DiscoverResponse(
            integration_status=self._get_integration_status(),
            service_prompts=self._build_service_prompts(),
            refreshing=True,
        )

    def _get_integration_status(self) -> dict[str, bool]:
        return {
            "listenbrainz": self._is_listenbrainz_enabled(),
            "jellyfin": self._is_jellyfin_enabled(),
            "lidarr": self._is_lidarr_configured(),
        }

    async def get_discover_preview(self) -> DiscoverPreview | None:
        if not self._memory_cache:
            return None
        cached = await self._memory_cache.get(DISCOVER_CACHE_KEY)
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

    async def warm_cache(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            response = await self.build_discover_data()
            if self._memory_cache and self._has_meaningful_content(response):
                await self._memory_cache.set(DISCOVER_CACHE_KEY, response, DISCOVER_CACHE_TTL)
                logger.info("Discover data built and cached successfully")
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
        )

    async def build_discover_data(self) -> DiscoverResponse:
        lb_enabled = self._is_listenbrainz_enabled()
        jf_enabled = self._is_jellyfin_enabled()
        lidarr_configured = self._is_lidarr_configured()
        username = self._get_listenbrainz_username()

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

        seed_artists = await self._get_seed_artists(lb_enabled, username, jf_enabled)

        tasks: dict[str, Any] = {}

        for i, seed in enumerate(seed_artists[:3]):
            mbid = seed.artist_mbids[0] if hasattr(seed, 'artist_mbids') and seed.artist_mbids else getattr(seed, 'artist_mbid', None)
            if mbid:
                tasks[f"similar_{i}"] = self._lb_repo.get_similar_artists(mbid, max_similar=20)

        tasks["lb_trending"] = self._lb_repo.get_sitewide_top_artists(count=20)

        if lb_enabled and username:
            tasks["lb_fresh"] = self._lb_repo.get_user_fresh_releases()
            tasks["lb_genres"] = self._lb_repo.get_user_genre_activity(username)

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
            seed_artists, results, library_mbids, seen_artist_mbids
        )
        logger.info("because_you_listen_to: %d sections", len(response.because_you_listen_to))

        response.fresh_releases = self._build_fresh_releases(results, library_mbids)

        response.missing_essentials = await self._build_missing_essentials(
            results, library_mbids
        )

        response.rediscover = self._build_rediscover(results, library_mbids, jf_enabled)

        response.artists_you_might_like = self._build_artists_you_might_like(
            seed_artists, results, library_mbids, seen_artist_mbids
        )

        response.popular_in_your_genres = await self._build_popular_in_genres(
            results, library_mbids, seen_artist_mbids
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

        response.globally_trending = self._build_globally_trending(
            results, library_mbids, seen_artist_mbids
        )

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
        }
        logger.info("Discover build complete: %s", sections_status)

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
        self, lb_enabled: bool, username: str | None, jf_enabled: bool
    ) -> list[ListenBrainzArtist]:
        seeds: list[ListenBrainzArtist] = []
        seen_mbids: set[str] = set()

        if lb_enabled and username:
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

        if len(seeds) < 3 and jf_enabled:
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

    def _build_because_sections(
        self,
        seed_artists: list,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
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
                mbid = artist.artist_mbid
                if not mbid:
                    continue
                if mbid.lower() in seen_artist_mbids:
                    continue
                items.append(HomeArtist(
                    mbid=mbid,
                    name=artist.artist_name,
                    listen_count=artist.listen_count,
                    in_library=mbid.lower() in library_mbids,
                ))
                seen_artist_mbids.add(mbid.lower())

            if not items:
                continue

            min_unique = 3
            if len(items) < min_unique and len(sections) > 0:
                continue

            sections.append(BecauseYouListenTo(
                seed_artist=seed_name,
                seed_artist_mbid=seed_mbid,
                listen_count=getattr(seed, 'listen_count', 0),
                section=HomeSection(
                    title=f"Because You Listen To {seed_name}",
                    type="artists",
                    items=items[:15],
                    source="listenbrainz",
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

        all_missing: list[HomeAlbum] = []
        for artist_mbid, _ in qualifying_artists[:10]:
            try:
                top_releases = await self._lb_repo.get_artist_top_release_groups(
                    artist_mbid, count=10
                )
                artist_missing = 0
                for rg in top_releases:
                    if artist_missing >= MISSING_ESSENTIALS_MAX_PER_ARTIST:
                        break
                    rg_mbid = rg.release_group_mbid
                    if not rg_mbid or rg_mbid.lower() in library_album_mbids:
                        continue
                    all_missing.append(HomeAlbum(
                        mbid=rg_mbid,
                        name=rg.release_group_name,
                        artist_name=rg.artist_name,
                        listen_count=rg.listen_count,
                        in_library=False,
                    ))
                    artist_missing += 1
            except Exception as e:
                logger.debug(f"Failed to get releases for artist {artist_mbid[:8]}: {e}")
                continue
            await asyncio.sleep(0.2)

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
                image_url = self._jf_repo.get_image_url(target_id, item.image_tag)

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
    ) -> HomeSection | None:
        aggregated: list[HomeArtist] = []
        for i in range(len(seed_artists[:3])):
            similar = results.get(f"similar_{i}")
            if not similar:
                continue
            for artist in similar:
                mbid = artist.artist_mbid
                if not mbid:
                    continue
                if mbid.lower() in seen_artist_mbids:
                    continue
                aggregated.append(HomeArtist(
                    mbid=mbid,
                    name=artist.artist_name,
                    listen_count=artist.listen_count,
                    in_library=mbid.lower() in library_mbids,
                ))
                seen_artist_mbids.add(mbid.lower())

        if not aggregated:
            return None

        aggregated.sort(key=lambda x: x.listen_count or 0, reverse=True)
        return HomeSection(
            title="Artists You Might Like",
            type="artists",
            items=aggregated[:15],
            source="listenbrainz",
        )

    async def _build_popular_in_genres(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
        seen_artist_mbids: set[str],
    ) -> HomeSection | None:
        genres = results.get("lb_genres")

        if not genres:
            return None
        else:
            genre_names = []
            for genre in genres[:3]:
                name = genre.genre if hasattr(genre, 'genre') else str(genre)
                genre_names.append(name)

        all_artists: list[HomeArtist] = []

        for genre_name in genre_names:
            try:
                tag_artists = await self._mb_repo.search_artists_by_tag(genre_name, limit=10)
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
            except Exception as e:
                logger.debug(f"Failed to search artists for genre '{genre_name}': {e}")
                continue

        if not all_artists:
            return None

        return HomeSection(
            title="Popular In Your Genres",
            type="artists",
            items=all_artists[:15],
            source="musicbrainz",
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
                description="Get personalized recommendations based on your listening history and discover similar artists.",
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

    async def build_queue(self, count: int = 10) -> DiscoverQueueResponse:
        lb_enabled = self._is_listenbrainz_enabled()
        jf_enabled = self._is_jellyfin_enabled()
        lidarr_configured = self._is_lidarr_configured()
        username = self._get_listenbrainz_username()

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

        has_services = lb_enabled or jf_enabled
        if has_services:
            items = await self._build_personalized_queue(
                count, lb_enabled, username, jf_enabled, ignored_mbids, library_album_mbids
            )
        else:
            items = await self._build_anonymous_queue(count, ignored_mbids, library_album_mbids)

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

    async def _build_personalized_queue(
        self,
        count: int,
        lb_enabled: bool,
        username: str | None,
        jf_enabled: bool,
        ignored_mbids: set[str],
        library_album_mbids: set[str],
    ) -> list[DiscoverQueueItemLight]:
        seed_artists = await self._get_seed_artists(lb_enabled, username, jf_enabled)
        if not seed_artists:
            return await self._build_anonymous_queue(count, ignored_mbids, library_album_mbids)

        seeds = seed_artists[:3]
        candidate_pools: list[list[DiscoverQueueItemLight]] = [[] for _ in range(len(seeds))]

        async def _process_seed(i: int, seed: Any) -> None:
            seed_mbid = seed.artist_mbids[0] if seed.artist_mbids else None
            if not seed_mbid:
                return
            try:
                similar = await self._lb_repo.get_similar_artists(seed_mbid, max_similar=15)
                for sim_artist in similar:
                    if not sim_artist.artist_mbid or sim_artist.artist_mbid.lower() == VARIOUS_ARTISTS_MBID:
                        continue
                    try:
                        release_groups = await self._lb_repo.get_artist_top_release_groups(
                            sim_artist.artist_mbid, count=5
                        )
                        for rg in release_groups:
                            rg_mbid = rg.release_group_mbid
                            if not rg_mbid:
                                continue
                            if rg_mbid.lower() in ignored_mbids or rg_mbid.lower() in library_album_mbids:
                                continue
                            cover_url = f"/api/covers/release-group/{rg_mbid}?size=500"
                            candidate_pools[i].append(DiscoverQueueItemLight(
                                release_group_mbid=rg_mbid,
                                album_name=rg.release_group_name,
                                artist_name=rg.artist_name,
                                artist_mbid=sim_artist.artist_mbid,
                                cover_url=cover_url,
                                recommendation_reason=f"Similar to {seed.artist_name}",
                                in_library=False,
                            ))
                    except Exception as e:
                        logger.debug(f"Failed to get releases for similar artist: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Failed to get similar artists for seed {seed_mbid[:8]}: {e}")

        await asyncio.gather(*[_process_seed(i, seed) for i, seed in enumerate(seeds)])

        wildcard_slots = 2
        personalized_target = max(count - wildcard_slots, 0)
        personalized = self._round_robin_select(candidate_pools, personalized_target)
        seen_mbids = {item.release_group_mbid.lower() for item in personalized}

        wildcard_count = max(wildcard_slots, count - len(personalized))
        wildcards = await self._get_wildcard_albums(wildcard_count, ignored_mbids, library_album_mbids, seen_mbids)

        return self._interleave_wildcards(personalized, wildcards)

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
    ) -> list[DiscoverQueueItemLight]:
        if count <= 0:
            return []
        exclude = ignored_mbids | library_album_mbids | (seen_mbids or set())
        wildcards: list[DiscoverQueueItemLight] = []

        decades = ["1970s", "1980s", "1990s", "2000s", "2010s"]
        sampled_decades = random.sample(decades, min(3, len(decades)))
        decade_offsets = [(d, random.randint(0, 200)) for d in sampled_decades]

        async def _fetch_trending():
            try:
                return await self._lb_repo.get_sitewide_top_release_groups(count=25)
            except Exception as e:
                logger.debug(f"Failed to get trending wildcards: {e}")
                return []

        async def _fetch_decade(decade: str, offset: int):
            try:
                return (decade, await self._mb_repo.search_release_groups_by_tag(
                    decade, limit=25, offset=offset
                ))
            except Exception as e:
                logger.debug(f"Failed to get decade wildcards for {decade}: {e}")
                return (decade, [])

        results = await asyncio.gather(
            _fetch_trending(),
            *[_fetch_decade(d, o) for d, o in decade_offsets],
        )

        trending = results[0]
        random.shuffle(trending)
        trending_target = min(count, 2)
        for rg in trending:
            if len(wildcards) >= trending_target:
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
            exclude.add(rg_mbid.lower())

        for decade, decade_results in results[1:]:
            if len(wildcards) >= count:
                break
            random.shuffle(decade_results)
            for rg in decade_results:
                if len(wildcards) >= count:
                    break
                rg_mbid = rg.musicbrainz_id
                if not rg_mbid or rg_mbid.lower() in exclude:
                    continue
                wildcards.append(DiscoverQueueItemLight(
                    release_group_mbid=rg_mbid,
                    album_name=rg.title,
                    artist_name=rg.artist or "Unknown",
                    artist_mbid="",
                    cover_url=f"/api/covers/release-group/{rg_mbid}?size=500",
                    recommendation_reason=f"Classic from the {decade}",
                    is_wildcard=True,
                    in_library=False,
                ))
                exclude.add(rg_mbid.lower())

        if len(wildcards) == 0:
            logger.warning("Failed to populate any wildcard albums for discover queue")

        return wildcards

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
        self, count: int, ignored_mbids: set[str], library_album_mbids: set[str]
    ) -> list[DiscoverQueueItemLight]:
        items: list[DiscoverQueueItemLight] = []
        half = count // 2

        try:
            trending = await self._lb_repo.get_sitewide_top_release_groups(count=50)
            random.shuffle(trending)
            for rg in trending:
                if len(items) >= half:
                    break
                rg_mbid = rg.release_group_mbid
                if not rg_mbid or rg_mbid.lower() in ignored_mbids or rg_mbid.lower() in library_album_mbids:
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

        decades = ["1970s", "1980s", "1990s", "2000s", "2010s"]
        remaining = count - len(items)
        if remaining > 0:
            decade = random.choice(decades)
            offset = random.randint(0, 200)
            try:
                decade_results = await self._mb_repo.search_release_groups_by_tag(
                    decade, limit=25, offset=offset
                )
                random.shuffle(decade_results)
                for rg in decade_results:
                    if len(items) >= count:
                        break
                    rg_mbid = rg.musicbrainz_id
                    if not rg_mbid or rg_mbid.lower() in ignored_mbids or rg_mbid.lower() in library_album_mbids:
                        continue
                    items.append(DiscoverQueueItemLight(
                        release_group_mbid=rg_mbid,
                        album_name=rg.title,
                        artist_name=rg.artist or "Unknown",
                        artist_mbid="",
                        cover_url=f"/api/covers/release-group/{rg_mbid}?size=500",
                        recommendation_reason=f"Classic from the {decade}",
                        is_wildcard=True,
                        in_library=False,
                    ))
            except Exception as e:
                logger.debug(f"Failed to get decade picks for anonymous queue: {e}")

        return items

    async def enrich_queue_item(self, release_group_mbid: str) -> DiscoverQueueEnrichment:
        cache_key = f"discover_queue_enrich:{release_group_mbid}"
        if self._memory_cache:
            cached = await self._memory_cache.get(cache_key)
            if cached is not None and isinstance(cached, DiscoverQueueEnrichment):
                return cached

        enrichment = DiscoverQueueEnrichment()

        rg_data = await self._mb_repo.get_release_group_by_id(
            release_group_mbid,
            includes=["artist-credits", "releases", "tags", "url-rels"],
        )

        artist_mbid = ""
        youtube_url = None

        if rg_data:
            tags_raw = rg_data.get("tag-list", [])
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

            releases = rg_data.get("release-list", [])
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
                            tracks = release_data.get("medium-list", [])
                            recordings_checked = 0
                            for medium in tracks:
                                for track in medium.get("track-list", []):
                                    if recordings_checked >= 3:
                                        break
                                    rec = track.get("recording", {})
                                    rec_id = rec.get("id")
                                    if rec_id:
                                        recordings_checked += 1
                                        rec_data = await self._mb_repo.get_recording_by_id(
                                            rec_id, includes=["url-rels"]
                                        )
                                        if rec_data:
                                            yt_raw = self._mb_repo.extract_youtube_url_from_relations(rec_data)
                                            if yt_raw:
                                                youtube_url = self._mb_repo.youtube_url_to_embed(yt_raw)
                                                break
                                if youtube_url or recordings_checked >= 3:
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
                        url_rels = mb_artist.get("url-relation-list", [])
                        wiki_url = None
                        for rel in url_rels:
                            if rel.get("type") in ("wikipedia", "wikidata"):
                                wiki_url = rel.get("target")
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

        await asyncio.gather(_get_artist_and_bio(), _get_listen_count())

        if self._memory_cache:
            await self._memory_cache.set(cache_key, enrichment, DISCOVER_QUEUE_ENRICH_TTL)

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

    async def get_ignored_releases(self) -> list[dict]:
        if self._library_cache:
            return await self._library_cache.get_ignored_releases()
        return []

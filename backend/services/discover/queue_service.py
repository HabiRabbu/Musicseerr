import asyncio
import logging
import random
import uuid
from typing import Any

from api.v1.schemas.discover import (
    DiscoverQueueItemLight,
    DiscoverQueueResponse,
    DiscoverIgnoredRelease,
    QueueSettings,
)
from infrastructure.persistence import LibraryDB, MBIDStore
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from repositories.listenbrainz_models import ListenBrainzArtist
from services.discover.integration_helpers import IntegrationHelpers
from services.discover.mbid_resolution_service import MbidResolutionService

logger = logging.getLogger(__name__)

VARIOUS_ARTISTS_MBID = "89ad4ac3-39f7-470e-963a-56509c546377"


class DiscoverQueueService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        jellyfin_repo: JellyfinRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        integration: IntegrationHelpers,
        mbid_resolution: MbidResolutionService,
        library_db: LibraryDB | None = None,
        mbid_store: MBIDStore | None = None,
        lastfm_repo: LastFmRepositoryProtocol | None = None,
    ) -> None:
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._mb_repo = musicbrainz_repo
        self._integration = integration
        self._mbid = mbid_resolution
        self._library_db = library_db
        self._mbid_store = mbid_store
        self._lfm_repo = lastfm_repo

    async def build_queue(self, count: int | None = None, source: str | None = None) -> DiscoverQueueResponse:
        qs = self._integration.get_queue_settings()
        if count is None:
            count = qs.queue_size
        resolved_source = self._integration.resolve_source(source)
        lb_enabled = self._integration.is_listenbrainz_enabled()
        jf_enabled = self._integration.is_jellyfin_enabled()
        lidarr_configured = self._integration.is_lidarr_configured()
        lfm_enabled = self._integration.is_lastfm_enabled()
        username = self._integration.get_listenbrainz_username()
        lfm_username = self._integration.get_lastfm_username()

        ignored_mbids: set[str] = set()
        if self._mbid_store:
            try:
                ignored_mbids = await self._mbid_store.get_ignored_release_mbids()
            except Exception:  # noqa: BLE001
                logger.warning("Failed to load ignored release MBIDs from cache")

        library_album_mbids = await self._mbid.get_library_album_mbids(lidarr_configured)
        listened_release_group_mbids = await self._mbid.get_user_listened_release_group_mbids(
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
            except Exception as e:  # noqa: BLE001
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
                except Exception as e:  # noqa: BLE001
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
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Failed to get Jellyfin seed artists: {e}")
                    continue

        return seeds

    async def validate_queue_mbids(self, mbids: list[str]) -> list[str]:
        library_mbids: set[str] = set()
        if self._library_db:
            try:
                library_mbids = await self._library_db.get_all_album_mbids()
            except Exception:  # noqa: BLE001
                logger.warning("Failed to load album MBIDs from library cache for validation")
        if not library_mbids:
            try:
                lidarr_configured = self._integration.is_lidarr_configured()
                if lidarr_configured:
                    library_mbids = await self._mbid.get_library_album_mbids(True)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to load album MBIDs from Lidarr for validation")
        if not library_mbids:
            return mbids
        lowered_library = {lm.lower() for lm in library_mbids}
        return [m for m in mbids if m.lower() in lowered_library]

    async def ignore_release(
        self, release_group_mbid: str, artist_mbid: str, release_name: str, artist_name: str
    ) -> None:
        if self._mbid_store:
            await self._mbid_store.add_ignored_release(
                release_group_mbid, artist_mbid, release_name, artist_name
            )

    async def get_ignored_releases(self) -> list[DiscoverIgnoredRelease]:
        if self._mbid_store:
            rows = await self._mbid_store.get_ignored_releases()
            return [DiscoverIgnoredRelease(**row) for row in rows]
        return []

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
                    sim_mbid = self._mbid.normalize_mbid(sim_artist.artist_mbid)
                    if not sim_mbid or sim_mbid == VARIOUS_ARTISTS_MBID:
                        continue

                    try:
                        release_groups = await self._lb_repo.get_artist_top_release_groups(
                            sim_mbid,
                            count=qs.albums_per_similar,
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"Failed to get releases for similar artist: {e}")
                        continue

                    for rg in release_groups:
                        rg_mbid = self._mbid.normalize_mbid(rg.release_group_mbid)
                        if not rg_mbid:
                            continue
                        if rg_mbid in excluded_mbids or rg_mbid in pool_seen:
                            continue
                        pools[i].append(
                            self._mbid.make_queue_item(
                                release_group_mbid=rg_mbid,
                                album_name=rg.release_group_name,
                                artist_name=rg.artist_name,
                                artist_mbid=sim_mbid,
                                reason=f"Similar to {seed.artist_name}",
                            )
                        )
                        pool_seen.add(rg_mbid)
            except Exception as e:  # noqa: BLE001
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
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch user genre activity from ListenBrainz")
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
                rg_mbid = self._mbid.normalize_mbid(getattr(release, "musicbrainz_id", None))
                if not rg_mbid:
                    continue
                if rg_mbid in excluded_mbids or rg_mbid in seen:
                    continue
                items.append(
                    self._mbid.make_queue_item(
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
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch fresh releases from ListenBrainz")
            return []

        if not fresh_releases:
            return []

        items: list[DiscoverQueueItemLight] = []
        seen: set[str] = set()
        for release in fresh_releases:
            if not isinstance(release, dict):
                continue
            rg_mbid = self._mbid.normalize_mbid(release.get("release_group_mbid"))
            if not rg_mbid:
                continue
            if rg_mbid in excluded_mbids or rg_mbid in seen:
                continue

            artist_mbids = release.get("artist_mbids")
            first_artist_mbid = ""
            if isinstance(artist_mbids, list) and artist_mbids:
                first_artist_mbid = self._mbid.normalize_mbid(artist_mbids[0]) or ""

            album_name = release.get("title") or release.get("release_group_name") or "Unknown"
            artist_name = release.get("artist_credit_name") or release.get("artist_name") or "Unknown"
            items.append(
                self._mbid.make_queue_item(
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
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch loved recordings from ListenBrainz")
            return []

        artist_mbids: list[str] = []
        seen_artists: set[str] = set()
        for recording in loved:
            mbids = getattr(recording, "artist_mbids", None) or []
            if not mbids:
                continue
            normalized = self._mbid.normalize_mbid(mbids[0])
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
                rg_mbid = self._mbid.normalize_mbid(rg.release_group_mbid)
                if not rg_mbid:
                    continue
                if rg_mbid in excluded_mbids or rg_mbid in seen_rg_mbids:
                    continue
                items.append(
                    self._mbid.make_queue_item(
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
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch top release groups from ListenBrainz for deep cuts")
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
            rg_artist_mbids = getattr(rg, "artist_mbids", None) or []
            if not rg_artist_mbids:
                continue
            artist_mbid = self._mbid.normalize_mbid(rg_artist_mbids[0])
            if not artist_mbid or artist_mbid in artist_seed_names:
                continue
            artist_seed_names[artist_mbid] = getattr(rg, "artist_name", "")
            if len(artist_seed_names) >= 6:
                break

        if not artist_seed_names:
            return []

        artist_mbid_list = list(artist_seed_names.keys())
        results = await asyncio.gather(
            *[
                self._lb_repo.get_artist_top_release_groups(
                    a_mbid,
                    count=max(albums_per_artist + 2, 4),
                )
                for a_mbid in artist_mbid_list
            ],
            return_exceptions=True,
        )

        items: list[DiscoverQueueItemLight] = []
        seen_rg_mbids: set[str] = set()
        for a_mbid, result in zip(artist_mbid_list, results):
            if isinstance(result, Exception):
                continue
            for rg in result:
                rg_mbid = self._mbid.normalize_mbid(rg.release_group_mbid)
                if not rg_mbid:
                    continue
                if rg_mbid in current_top_mbids or rg_mbid in listened_mbids:
                    continue
                if rg_mbid in excluded_mbids or rg_mbid in seen_rg_mbids:
                    continue

                source_artist_name = artist_seed_names.get(a_mbid) or rg.artist_name
                items.append(
                    self._mbid.make_queue_item(
                        release_group_mbid=rg_mbid,
                        album_name=rg.release_group_name,
                        artist_name=rg.artist_name,
                        artist_mbid=a_mbid,
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

        qs = self._integration.get_queue_settings()
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
                        if self._mbid.normalize_mbid(sim.mbid)
                        and self._mbid.normalize_mbid(sim.mbid) != VARIOUS_ARTISTS_MBID
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
                    candidate_pools[i] = await self._mbid.lastfm_albums_to_queue_items(
                        sim_albums_map,
                        exclude=excluded_mbids,
                        target=seed_target,
                        reason=f"Similar to {seed.artist_name}",
                        resolver_cache=mbid_resolution_cache,
                        use_album_artist_name=False,
                    )
                except Exception as e:  # noqa: BLE001
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
            elif isinstance(similar_seed_pools, Exception):
                logger.warning("Strategy similar_seeds FAILED: %s", similar_seed_pools)

            for idx, strategy_result in enumerate(strategy_results[1:], start=1):
                name = strategy_names[idx]
                if isinstance(strategy_result, Exception):
                    logger.warning("Strategy %s FAILED: %s", name, strategy_result)
                    continue
                if strategy_result:
                    candidate_pools.append(strategy_result)

        personalized = self._round_robin_select(candidate_pools, personalized_target)
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
        use_lastfm = resolved_source == "lastfm" and self._integration.is_lastfm_enabled() and self._lfm_repo is not None
        target = max(count * 2, 6)

        try:
            if use_lastfm:
                top_artists = await self._lfm_repo.get_global_top_artists(limit=15)
                random.shuffle(top_artists)
                valid_artists = [
                    a
                    for a in top_artists[:10]
                    if self._mbid.normalize_mbid(a.mbid) != VARIOUS_ARTISTS_MBID
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
                wildcards = await self._mbid.lastfm_albums_to_queue_items(
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
                        cover_url=f"/api/v1/covers/release-group/{rg_mbid}?size=500",
                        recommendation_reason="Trending This Week",
                        is_wildcard=True,
                        in_library=False,
                    ))
        except Exception as e:  # noqa: BLE001
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
                    except Exception:  # noqa: BLE001
                        logger.warning("Failed to search release groups for decade tag %s", decade)
                        continue
                    for release in decade_releases:
                        if len(wildcards) >= target:
                            break
                        rg_mbid = self._mbid.normalize_mbid(getattr(release, "musicbrainz_id", None))
                        if not rg_mbid or rg_mbid.lower() in exclude:
                            continue
                        wildcards.append(DiscoverQueueItemLight(
                            release_group_mbid=rg_mbid,
                            album_name=getattr(release, "title", "Unknown"),
                            artist_name=getattr(release, "artist", "Unknown") or "Unknown",
                            artist_mbid="",
                            cover_url=f"/api/v1/covers/release-group/{rg_mbid}?size=500",
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
        use_lastfm = resolved_source == "lastfm" and self._integration.is_lastfm_enabled() and self._lfm_repo is not None
        exclude = ignored_mbids | library_album_mbids

        try:
            if use_lastfm:
                top_artists = await self._lfm_repo.get_global_top_artists(limit=15)
                random.shuffle(top_artists)
                valid_artists = [
                    a
                    for a in top_artists
                    if self._mbid.normalize_mbid(a.mbid) != VARIOUS_ARTISTS_MBID
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
                items = await self._mbid.lastfm_albums_to_queue_items(
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
                        cover_url=f"/api/v1/covers/release-group/{rg_mbid}?size=500",
                        recommendation_reason="Trending This Week",
                        is_wildcard=True,
                        in_library=False,
                    ))
        except Exception as e:  # noqa: BLE001
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

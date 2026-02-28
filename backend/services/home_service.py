import asyncio
import logging
from typing import Any
from api.v1.schemas.home import (
    HomeResponse,
    HomeSection,
    HomeGenre,
    ServicePrompt,
    HomeArtist,
    DiscoverPreview,
    HomeIntegrationStatus,
)
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from api.v1.schemas.library import LibraryAlbum
from services.preferences_service import PreferencesService
from services.home_transformers import HomeDataTransformers
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.http.deduplication import deduplicate

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
    ):
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._preferences = preferences_service
        self._memory_cache = memory_cache
        self._lfm_repo = lastfm_repo
        self._transformers = HomeDataTransformers(jellyfin_repo)
    
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

    def _is_local_files_enabled(self) -> bool:
        lf_settings = self._preferences.get_local_files_connection()
        return lf_settings.enabled and bool(lf_settings.music_path)

    def _is_lastfm_enabled(self) -> bool:
        return self._preferences.is_lastfm_enabled()
    
    def _get_listenbrainz_username(self) -> str | None:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.username if lb_settings.enabled else None

    def _get_lastfm_username(self) -> str | None:
        lf_settings = self._preferences.get_lastfm_connection()
        return lf_settings.username if lf_settings.enabled else None

    def _resolve_source(self, source: str | None) -> str:
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

    def get_integration_status(self) -> HomeIntegrationStatus:
        return HomeIntegrationStatus(
            listenbrainz=self._is_listenbrainz_enabled(),
            jellyfin=self._is_jellyfin_enabled(),
            lidarr=self._is_lidarr_configured(),
            youtube=self._is_youtube_enabled(),
            localfiles=self._is_local_files_enabled(),
            lastfm=self._is_lastfm_enabled(),
        )

    async def get_genre_artist(self, genre_name: str) -> str | None:
        VARIOUS_ARTISTS_MBID = "89ad4ac3-39f7-470e-963a-56509c546377"
        CACHE_TTL = 24 * 60 * 60
        
        cache_key = f"genre_artist:{genre_name.lower()}"
        
        if self._memory_cache:
            cached = await self._memory_cache.get(cache_key)
            if cached is not None:
                return cached if cached != "" else None
        
        try:
            artists = await self._mb_repo.search_artists_by_tag(genre_name, limit=10)
            for artist in artists:
                if artist.musicbrainz_id and artist.musicbrainz_id != VARIOUS_ARTISTS_MBID:
                    if self._memory_cache:
                        await self._memory_cache.set(cache_key, artist.musicbrainz_id, CACHE_TTL)
                    return artist.musicbrainz_id
        except Exception as e:
            logger.warning(f"Failed to fetch artist for genre '{genre_name}': {e}")
        
        if self._memory_cache:
            await self._memory_cache.set(cache_key, "", CACHE_TTL)
        
        return None
    
    async def get_genre_artists_batch(self, genres: list[str]) -> dict[str, str | None]:
        if not genres:
            return {}
        
        tasks = {genre: self.get_genre_artist(genre) for genre in genres[:20]}
        results = await self._execute_tasks(tasks)
        return {genre: mbid for genre, mbid in results.items()}
    
    def _get_home_cache_key(self, source: str | None = None) -> str:
        resolved = self._resolve_source(source)
        lb_enabled = self._is_listenbrainz_enabled()
        lfm_enabled = self._is_lastfm_enabled()
        lb_username = self._get_listenbrainz_username() or ""
        lfm_username = self._get_lastfm_username() or ""
        return f"home_response:{resolved}:{lb_enabled}:{lfm_enabled}:{lb_username}:{lfm_username}"
    
    async def get_cached_home_data(self) -> HomeResponse | None:
        if not self._memory_cache:
            return None
        cache_key = self._get_home_cache_key()
        return await self._memory_cache.get(cache_key)

    @deduplicate(lambda self, source=None: self._get_home_cache_key(source))
    async def get_home_data(self, source: str | None = None) -> HomeResponse:
        HOME_CACHE_TTL = 300
        resolved_source = self._resolve_source(source)
        
        if self._memory_cache:
            cache_key = self._get_home_cache_key(source)
            cached = await self._memory_cache.get(cache_key)
            if cached is not None:
                return cached
        
        integration_status = self.get_integration_status()
        lb_enabled = integration_status.listenbrainz
        lidarr_configured = integration_status.lidarr
        lfm_enabled = integration_status.lastfm
        username = self._get_listenbrainz_username()
        lfm_username = self._get_lastfm_username()
        
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
        elif resolved_source == "lastfm" and self._lfm_repo and lfm_enabled and lfm_username:
            tasks["lfm_recent"] = self._lfm_repo.get_user_recent_tracks(
                lfm_username, limit=20
            )
            tasks["lfm_loved"] = self._lfm_repo.get_user_loved_tracks(
                lfm_username, limit=20
            )
        
        results = await self._execute_tasks(tasks)
        
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
        
        response.recently_added = self._build_recently_added_section(recently_imported)
        response.library_artists = self._build_library_artists_section(library_artists)
        response.library_albums = self._build_library_albums_section(library_albums)

        if resolved_source == "listenbrainz":
            response.trending_artists = self._build_trending_artists_section(
                results, library_artist_mbids
            )
            response.popular_albums = self._build_popular_albums_section(
                results, library_album_mbids
            )
            response.your_top_albums = self._build_lb_user_top_albums_section(
                results, library_album_mbids
            )
            response.recently_played = self._build_listenbrainz_recent_section(results)
            response.favorite_artists = self._build_listenbrainz_favorites_section(results)
        elif resolved_source == "lastfm":
            response.trending_artists = self._build_lastfm_trending_section(
                results, library_artist_mbids
            )
            response.your_top_albums = self._build_lastfm_top_albums_section(
                results, library_album_mbids
            )
            response.recently_played = self._build_lastfm_recent_section(results)
            response.favorite_artists = self._build_lastfm_favorites_section(results)

        response.genre_list = self._build_genre_list_section(
            library_albums,
            results.get("lb_genres") if resolved_source == "listenbrainz" else None,
        )
        
        if response.genre_list and response.genre_list.items:
            genre_names = [
                g.name for g in response.genre_list.items[:20]
                if isinstance(g, HomeGenre)
            ]
            response.genre_artists = await self.get_genre_artists_batch(genre_names)
        
        response.service_prompts = self._build_service_prompts(
            lb_enabled,
            lidarr_configured,
            lfm_enabled,
        )

        response.discover_preview = await self._build_discover_preview()
        
        if self._memory_cache:
            cache_key = self._get_home_cache_key(source)
            await self._memory_cache.set(cache_key, response, HOME_CACHE_TTL)
        
        return response
    
    async def _execute_tasks(self, tasks: dict[str, Any]) -> dict[str, Any]:
        if not tasks:
            return {}
        
        keys = list(tasks.keys())
        coros = list(tasks.values())
        
        raw_results = await asyncio.gather(*coros, return_exceptions=True)
        
        results = {}
        for key, result in zip(keys, raw_results):
            if isinstance(result, Exception):
                logger.warning(f"Task {key} failed: {result}")
                results[key] = None
            else:
                results[key] = result
        
        return results
    
    def _build_recently_added_section(
        self,
        recently_imported: list[LibraryAlbum]
    ) -> HomeSection:
        return HomeSection(
            title="Recently Added",
            type="albums",
            items=[self._transformers.lidarr_album_to_home(a) for a in recently_imported[:15]],
            source="lidarr",
        )

    def _build_library_artists_section(self, library_artists: list[dict]) -> HomeSection:
        sorted_artists = sorted(
            library_artists, key=lambda x: x.get("album_count", 0), reverse=True
        )[:15]
        items = [
            a for a in (self._transformers.lidarr_artist_to_home(artist) for artist in sorted_artists)
            if a is not None
        ]
        return HomeSection(title="Your Artists", type="artists", items=items, source="lidarr")

    def _build_library_albums_section(self, library_albums: list[LibraryAlbum]) -> HomeSection:
        sorted_albums = sorted(
            library_albums, key=lambda x: (x.year or 0, x.album or ""), reverse=True
        )[:15]
        return HomeSection(
            title="Your Albums",
            type="albums",
            items=[self._transformers.lidarr_album_to_home(a) for a in sorted_albums],
            source="lidarr",
        )

    def _build_trending_artists_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection:
        artists = results.get("lb_trending_artists") or []
        items = [
            a for a in (self._transformers.lb_artist_to_home(artist, library_mbids) for artist in artists[:15])
            if a is not None
        ]
        return HomeSection(
            title="Trending Artists",
            type="artists",
            items=items,
            source="listenbrainz" if artists else None,
        )

    def _build_popular_albums_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection:
        albums = results.get("lb_trending_albums") or []
        return HomeSection(
            title="Popular Right Now",
            type="albums",
            items=[self._transformers.lb_release_to_home(a, library_mbids) for a in albums[:15]],
            source="listenbrainz" if albums else None,
        )

    def _build_lb_user_top_albums_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        release_groups = results.get("lb_user_top_rgs") or []
        if not release_groups:
            return None
        items = [
            self._transformers.lb_release_to_home(rg, library_mbids)
            for rg in release_groups[:15]
        ]
        return HomeSection(
            title="Your Top Albums",
            type="albums",
            items=items,
            source="listenbrainz",
        )

    def _build_genre_list_section(
        self, library_albums: list[LibraryAlbum], lb_genres: list | None = None
    ) -> HomeSection:
        genres = self._transformers.extract_genres_from_library(library_albums, lb_genres)
        source = "listenbrainz" if lb_genres else ("lidarr" if library_albums else None)
        return HomeSection(title="Browse by Genre", type="genres", items=genres, source=source)

    def _build_fresh_releases_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        releases = results.get("lb_fresh")
        if not releases:
            return None
        return HomeSection(
            title="New From Artists You Follow",
            type="albums",
            items=[self._transformers.lb_release_to_home(r, library_mbids) for r in releases[:15]],
            source="listenbrainz",
        )

    def _build_recommended_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        artists = results.get("lb_top_artists")
        if not artists:
            return None
        items = [
            a for a in (self._transformers.lb_artist_to_home(artist, library_mbids) for artist in artists[:15])
            if a is not None
        ]
        return HomeSection(
            title="Based on Your Listening", type="artists", items=items, source="listenbrainz"
        )

    def _build_listenbrainz_recent_section(self, results: dict[str, Any]) -> HomeSection | None:
        listens = results.get("lb_listens") or []
        if not listens:
            return None
        items = [
            self._transformers.lb_listen_to_home_track(listen)
            for listen in listens[:15]
        ]
        return HomeSection(
            title="Recently Scrobbled",
            type="tracks",
            items=items,
            source="listenbrainz",
        )

    def _build_listenbrainz_favorites_section(self, results: dict[str, Any]) -> HomeSection | None:
        loved = results.get("lb_loved") or []
        if not loved:
            return None
        items = [
            self._transformers.lb_feedback_to_home_track(recording)
            for recording in loved[:15]
        ]
        return HomeSection(
            title="Your Favorites",
            type="tracks",
            items=items,
            source="listenbrainz",
        )

    def _build_lastfm_trending_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection:
        artists = results.get("lfm_global_top_artists") or []
        items = [
            a for a in (
                self._transformers.lastfm_artist_to_home(artist, library_mbids)
                for artist in artists[:15]
            )
            if a is not None
        ]
        return HomeSection(
            title="Trending Artists",
            type="artists",
            items=items,
            source="lastfm" if artists else None,
        )

    def _build_lastfm_top_albums_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection:
        albums = results.get("lfm_top_albums") or []
        items = [
            a for a in (
                self._transformers.lastfm_album_to_home(album, library_mbids)
                for album in albums[:15]
            )
            if a is not None
        ]

        return HomeSection(
            title="Your Top Albums",
            type="albums",
            items=items,
            source="lastfm" if albums else None,
        )

    def _build_lastfm_recommended_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        artists = results.get("lfm_top_artists") or []
        if not artists:
            return None
        items = [
            a for a in (
                self._transformers.lastfm_artist_to_home(artist, library_mbids)
                for artist in artists[:15]
            )
            if a is not None
        ]
        if not items:
            return None
        return HomeSection(
            title="Based on Your Listening",
            type="artists",
            items=items,
            source="lastfm",
        )

    def _build_lastfm_recent_section(self, results: dict[str, Any]) -> HomeSection | None:
        tracks = results.get("lfm_recent") or []
        if not tracks:
            return None

        items = [
            self._transformers.lastfm_recent_to_home_track(track)
            for track in tracks[:15]
        ]
        if not items:
            return None
        return HomeSection(
            title="Recently Scrobbled",
            type="tracks",
            items=items,
            source="lastfm",
        )

    def _build_lastfm_favorites_section(self, results: dict[str, Any]) -> HomeSection | None:
        tracks = results.get("lfm_loved") or []
        if not tracks:
            return None
        items = [
            self._transformers.lastfm_loved_to_home_track(track)
            for track in tracks[:15]
        ]
        return HomeSection(
            title="Your Favorites",
            type="tracks",
            items=items,
            source="lastfm",
        )

    async def _resolve_release_mbids(self, release_ids: list[str]) -> dict[str, str]:
        if not release_ids:
            return {}
        tasks = [self._mb_repo.get_release_group_id_from_release(rid) for rid in release_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        rg_map: dict[str, str] = {}
        for rid, rg_id in zip(release_ids, results):
            if isinstance(rg_id, str) and rg_id:
                rg_map[rid] = rg_id
        return rg_map
    
    async def _build_discover_preview(self) -> DiscoverPreview | None:
        if not self._memory_cache:
            return None
        try:
            from api.v1.schemas.discover import DiscoverResponse as DR
            resolved = self._resolve_source(None)
            cache_key = f"discover_response:{resolved}"
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
        except Exception as e:
            logger.debug(f"Could not build discover preview: {e}")
            return None

    def _build_service_prompts(
        self,
        lb_enabled: bool,
        lidarr_configured: bool = True,
        lfm_enabled: bool = False,
    ) -> list[ServicePrompt]:
        prompts = []
        
        if not lidarr_configured:
            prompts.append(ServicePrompt(
                service="lidarr-connection",
                title="Connect Lidarr",
                description="Lidarr is required to manage your music library, request albums, and track your collection. Set up the connection to get started.",
                icon="🎶",
                color="accent",
                features=["Music library management", "Album requests", "Collection tracking", "Automatic imports"],
            ))
        
        if not lb_enabled and not lfm_enabled:
            prompts.append(ServicePrompt(
                service="listenbrainz",
                title="Connect ListenBrainz",
                description="Get personalized recommendations based on your listening history, discover new releases from artists you love, and see your top genres. You can also connect Last.fm for global listener stats.",
                icon="🎵",
                color="primary",
                features=["Personalized recommendations", "New release alerts", "Listening stats", "Top genres"],
            ))

        if not lfm_enabled and not lb_enabled:
            prompts.append(ServicePrompt(
                service="lastfm",
                title="Connect Last.fm",
                description="Scrobble your plays, see global listener stats, and get recommendations powered by Last.fm's music data.",
                icon="🎸",
                color="primary",
                features=["Scrobbling", "Global listener stats", "Artist recommendations", "Play history"],
            ))
        
        return prompts

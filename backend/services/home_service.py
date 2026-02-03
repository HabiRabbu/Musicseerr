import asyncio
import logging
from typing import Any
from api.v1.schemas.home import (
    HomeResponse,
    HomeSection,
    HomeGenre,
    ServicePrompt,
)
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
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
    ):
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._preferences = preferences_service
        self._memory_cache = memory_cache
        self._transformers = HomeDataTransformers(jellyfin_repo)
    
    def _is_listenbrainz_enabled(self) -> bool:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.enabled and bool(lb_settings.username)
    
    def _is_jellyfin_enabled(self) -> bool:
        jf_settings = self._preferences.get_jellyfin_connection()
        return jf_settings.enabled and bool(jf_settings.jellyfin_url) and bool(jf_settings.api_key)
    
    def _get_listenbrainz_username(self) -> str | None:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.username if lb_settings.enabled else None

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
    
    def _get_home_cache_key(self) -> str:
        lb_enabled = self._is_listenbrainz_enabled()
        jf_enabled = self._is_jellyfin_enabled()
        username = self._get_listenbrainz_username() or ""
        return f"home_response:{lb_enabled}:{jf_enabled}:{username}"
    
    async def get_cached_home_data(self) -> HomeResponse | None:
        if not self._memory_cache:
            return None
        cache_key = self._get_home_cache_key()
        return await self._memory_cache.get(cache_key)

    @deduplicate(lambda self: self._get_home_cache_key())
    async def get_home_data(self) -> HomeResponse:
        HOME_CACHE_TTL = 300
        
        if self._memory_cache:
            cache_key = self._get_home_cache_key()
            cached = await self._memory_cache.get(cache_key)
            if cached is not None:
                return cached
        
        lb_enabled = self._is_listenbrainz_enabled()
        jf_enabled = self._is_jellyfin_enabled()
        username = self._get_listenbrainz_username()
        
        tasks: dict[str, Any] = {
            "library_albums": self._lidarr_repo.get_library(),
            "library_artists": self._lidarr_repo.get_artists_from_library(),
            "recently_imported": self._lidarr_repo.get_recently_imported(limit=15),
            "lb_trending_artists": self._lb_repo.get_sitewide_top_artists(count=20),
            "lb_trending_albums": self._lb_repo.get_sitewide_top_release_groups(count=20),
        }
        
        if lb_enabled and username:
            lb_settings = self._preferences.get_listenbrainz_connection()
            self._lb_repo.configure(username=username, user_token=lb_settings.user_token)
            tasks["lb_top_artists"] = self._lb_repo.get_user_top_artists(count=20)
            tasks["lb_listens"] = self._lb_repo.get_user_listens(count=20)
            tasks["lb_fresh"] = self._lb_repo.get_user_fresh_releases()
            tasks["lb_genres"] = self._lb_repo.get_user_genre_activity(username)
        
        if jf_enabled:
            jf_settings = self._preferences.get_jellyfin_connection()
            self._jf_repo.configure(
                base_url=jf_settings.jellyfin_url,
                api_key=jf_settings.api_key,
                user_id=jf_settings.user_id
            )
            tasks["jf_recent"] = self._jf_repo.get_recently_played(limit=20)
            tasks["jf_favorites"] = self._jf_repo.get_favorite_artists(limit=20)
        
        results = await self._execute_tasks(tasks)
        
        library_albums: list[LibraryAlbum] = results.get("library_albums") or []
        library_artists: list[dict] = results.get("library_artists") or []
        recently_imported: list[LibraryAlbum] = results.get("recently_imported") or []
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}
        
        response = HomeResponse(
            integration_status={
                "listenbrainz": lb_enabled,
                "jellyfin": jf_enabled,
                "lidarr": len(library_albums) > 0,
            }
        )
        
        response.recently_added = self._build_recently_added_section(recently_imported)
        response.library_artists = self._build_library_artists_section(library_artists)
        response.library_albums = self._build_library_albums_section(library_albums)
        response.trending_artists = self._build_trending_artists_section(
            results, library_mbids
        )
        response.popular_albums = self._build_popular_albums_section(
            results, library_mbids
        )
        response.genre_list = self._build_genre_list_section(
            library_albums, results.get("lb_genres")
        )
        
        if response.genre_list and response.genre_list.items:
            genre_names = [
                g.name for g in response.genre_list.items[:20]
                if isinstance(g, HomeGenre)
            ]
            response.genre_artists = await self.get_genre_artists_batch(genre_names)
        
        if lb_enabled:
            response.fresh_releases = self._build_fresh_releases_section(
                results, library_mbids
            )
            response.recommended_artists = self._build_recommended_section(
                results, library_mbids
            )
        
        if jf_enabled:
            response.recently_played = self._build_recently_played_section(
                results, library_mbids
            )
            response.favorite_artists = self._build_favorites_section(
                results, library_mbids
            )
        
        response.service_prompts = self._build_service_prompts(lb_enabled, jf_enabled)
        
        if self._memory_cache:
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

    def _build_recently_played_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        items = results.get("jf_recent")
        if not items:
            return None
        seen_artists: set[str] = set()
        artist_items = []
        for item in items:
            artist = self._transformers.jf_item_to_artist(item, library_mbids)
            if artist and artist.name.lower() not in seen_artists:
                seen_artists.add(artist.name.lower())
                artist_items.append(artist)
                if len(artist_items) >= 15:
                    break
        if not artist_items:
            return None
        return HomeSection(title="Recently Played", type="artists", items=artist_items, source="jellyfin")

    def _build_favorites_section(
        self, results: dict[str, Any], library_mbids: set[str]
    ) -> HomeSection | None:
        favorites = results.get("jf_favorites")
        if not favorites:
            return None
        items = [
            a for a in (self._transformers.jf_item_to_artist(f, library_mbids) for f in favorites[:15])
            if a is not None
        ]
        if not items:
            return None
        return HomeSection(title="Your Favorites", type="artists", items=items, source="jellyfin")
    
    def _build_service_prompts(
        self,
        lb_enabled: bool,
        jf_enabled: bool
    ) -> list[ServicePrompt]:
        prompts = []
        
        if not lb_enabled:
            prompts.append(ServicePrompt(
                service="listenbrainz",
                title="Connect ListenBrainz",
                description="Get personalized recommendations based on your listening history, discover new releases from artists you love, and see your top genres.",
                icon="🎵",
                color="primary",
                features=["Personalized recommendations", "New release alerts", "Listening stats", "Top genres"],
            ))
        
        if not jf_enabled:
            prompts.append(ServicePrompt(
                service="jellyfin",
                title="Connect Jellyfin",
                description="See your recently played tracks, favorite artists, and get recommendations based on your media server's play history.",
                icon="📺",
                color="secondary",
                features=["Recently played", "Play statistics", "Favorite artists", "Listening history"],
            ))
        
        
        return prompts

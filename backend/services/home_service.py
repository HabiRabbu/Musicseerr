import asyncio
import logging
from typing import Any
from api.v1.schemas.home import (
    HomeResponse,
    HomeSection,
    HomeArtist,
    HomeAlbum,
    HomeGenre,
    GenreDetailResponse,
    GenreLibrarySection,
    GenrePopularSection,
    ServicePrompt,
    TrendingArtistsResponse,
    TrendingTimeRange,
    TrendingArtistsRangeResponse,
    PopularAlbumsResponse,
    PopularTimeRange,
    PopularAlbumsRangeResponse,
)
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    ListenBrainzArtist,
    ListenBrainzReleaseGroup,
    JellyfinItem,
)
from repositories.lidarr_repository import LibraryAlbum
from services.preferences_service import PreferencesService
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.cache.memory_cache import CacheInterface

logger = logging.getLogger(__name__)


class HomeService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        jellyfin_repo: JellyfinRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
        library_cache: LibraryCache | None = None,
        memory_cache: CacheInterface | None = None,
    ):
        self._lb_repo = listenbrainz_repo
        self._jf_repo = jellyfin_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._preferences = preferences_service
        self._library_cache = library_cache
        self._memory_cache = memory_cache
    
    def _is_listenbrainz_enabled(self) -> bool:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.enabled and bool(lb_settings.username)
    
    def _is_jellyfin_enabled(self) -> bool:
        jf_settings = self._preferences.get_jellyfin_connection()
        return jf_settings.enabled and self._jf_repo.is_configured()
    
    def _get_listenbrainz_username(self) -> str | None:
        lb_settings = self._preferences.get_listenbrainz_connection()
        return lb_settings.username if lb_settings.enabled else None
    
    def _lidarr_album_to_home(self, album: LibraryAlbum) -> HomeAlbum:
        return HomeAlbum(
            mbid=album.musicbrainz_id,
            name=album.album or "Unknown Album",
            artist_name=album.artist,
            artist_mbid=album.artist_mbid,
            image_url=album.cover_url,
            release_date=str(album.year) if album.year else None,
            in_library=True,
        )
    
    def _lidarr_artist_to_home(self, artist_data: dict) -> HomeArtist | None:
        mbid = artist_data.get("mbid")
        if not mbid:
            return None
        return HomeArtist(
            mbid=mbid,
            name=artist_data.get("name", "Unknown Artist"),
            image_url=None,
            listen_count=artist_data.get("album_count"),
            in_library=True,
        )
    
    def _lb_artist_to_home(
        self,
        artist: ListenBrainzArtist,
        library_mbids: set[str]
    ) -> HomeArtist | None:
        mbid = artist.artist_mbids[0] if artist.artist_mbids else None
        if not mbid:
            return None
        return HomeArtist(
            mbid=mbid,
            name=artist.artist_name,
            image_url=None,
            listen_count=artist.listen_count,
            in_library=mbid.lower() in library_mbids,
        )
    
    def _lb_release_to_home(
        self,
        release: ListenBrainzReleaseGroup,
        library_mbids: set[str]
    ) -> HomeAlbum:
        artist_mbid = release.artist_mbids[0] if release.artist_mbids else None
        return HomeAlbum(
            mbid=release.release_group_mbid,
            name=release.release_group_name,
            artist_name=release.artist_name,
            artist_mbid=artist_mbid,
            image_url=None,
            release_date=None,
            listen_count=release.listen_count,
            in_library=(release.release_group_mbid or "").lower() in library_mbids,
        )
    
    def _jf_item_to_artist(
        self,
        item: JellyfinItem,
        library_mbids: set[str]
    ) -> HomeArtist | None:
        mbid = None
        if item.provider_ids:
            mbid = item.provider_ids.get("MusicBrainzArtist")
        
        if not mbid:
            return None
        
        return HomeArtist(
            mbid=mbid,
            name=item.name,
            image_url=self._jf_repo.get_image_url(item.id, item.image_tag),
            listen_count=item.play_count,
            in_library=mbid.lower() in library_mbids,
        )
    
    def _extract_genres_from_library(
        self,
        albums: list[LibraryAlbum],
        lb_genres: list | None = None
    ) -> list[HomeGenre]:
        if lb_genres:
            return [
                HomeGenre(name=g.genre, listen_count=g.listen_count)
                for g in lb_genres[:20]
            ]

        default_genres = [
            "Rock", "Pop", "Hip Hop", "Electronic", "Jazz",
            "Classical", "R&B", "Country", "Metal", "Folk",
            "Blues", "Reggae", "Soul", "Punk", "Indie",
            "Alternative", "Dance", "Soundtrack", "World", "Latin"
        ]
        
        return [HomeGenre(name=g) for g in default_genres]
    
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
    
    async def get_home_data(self) -> HomeResponse:
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
            self._lb_repo.configure(username=username)
            tasks["lb_top_artists"] = self._lb_repo.get_user_top_artists(count=20)
            tasks["lb_listens"] = self._lb_repo.get_user_listens(count=20)
            tasks["lb_fresh"] = self._lb_repo.get_user_fresh_releases()
            tasks["lb_genres"] = self._lb_repo.get_user_genre_activity(username)
        
        if jf_enabled:
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
            items=[self._lidarr_album_to_home(a) for a in recently_imported[:15]],
            source="lidarr",
        )
    
    def _build_library_artists_section(
        self,
        library_artists: list[dict]
    ) -> HomeSection:
        sorted_artists = sorted(
            library_artists,
            key=lambda x: x.get("album_count", 0),
            reverse=True
        )[:15]
        
        return HomeSection(
            title="Your Artists",
            type="artists",
            items=[a for a in (self._lidarr_artist_to_home(artist) for artist in sorted_artists) if a is not None],
            source="lidarr",
        )
    
    def _build_library_albums_section(
        self,
        library_albums: list[LibraryAlbum]
    ) -> HomeSection:
        sorted_albums = sorted(
            library_albums,
            key=lambda x: (x.year or 0, x.album or ""),
            reverse=True
        )[:15]
        
        return HomeSection(
            title="Your Albums",
            type="albums",
            items=[self._lidarr_album_to_home(a) for a in sorted_albums],
            source="lidarr",
        )
    
    def _build_trending_artists_section(
        self,
        results: dict[str, Any],
        library_mbids: set[str]
    ) -> HomeSection:
        artists = results.get("lb_trending_artists") or []
        return HomeSection(
            title="Trending Artists",
            type="artists",
            items=[a for a in (self._lb_artist_to_home(artist, library_mbids) for artist in artists[:15]) if a is not None],
            source="listenbrainz" if artists else None,
        )
    
    def _build_popular_albums_section(
        self,
        results: dict[str, Any],
        library_mbids: set[str]
    ) -> HomeSection:
        albums = results.get("lb_trending_albums") or []
        return HomeSection(
            title="Popular Right Now",
            type="albums",
            items=[self._lb_release_to_home(a, library_mbids) for a in albums[:15]],
            source="listenbrainz" if albums else None,
        )
    
    def _build_genre_list_section(
        self,
        library_albums: list[LibraryAlbum],
        lb_genres: list | None = None
    ) -> HomeSection:
        genres = self._extract_genres_from_library(library_albums, lb_genres)
        source = "listenbrainz" if lb_genres else ("lidarr" if library_albums else None)
        return HomeSection(
            title="Browse by Genre",
            type="genres",
            items=genres,
            source=source,
        )
    
    def _build_fresh_releases_section(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
    ) -> HomeSection | None:
        releases = results.get("lb_fresh")
        if not releases:
            return None
        
        return HomeSection(
            title="New From Artists You Follow",
            type="albums",
            items=[self._lb_release_to_home(r, library_mbids) for r in releases[:15]],
            source="listenbrainz",
        )
    
    def _build_recommended_section(
        self,
        results: dict[str, Any],
        library_mbids: set[str]
    ) -> HomeSection | None:
        artists = results.get("lb_top_artists")
        if not artists:
            return None
        
        return HomeSection(
            title="Based on Your Listening",
            type="artists",
            items=[a for a in (self._lb_artist_to_home(artist, library_mbids) for artist in artists[:15]) if a is not None],
            source="listenbrainz",
        )
    
    def _build_recently_played_section(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
    ) -> HomeSection | None:
        items = results.get("jf_recent")
        if not items:
            return None
        
        return HomeSection(
            title="Recently Played",
            type="artists",
            items=[a for a in (self._jf_item_to_artist(i, library_mbids) for i in items[:15]) if a is not None],
            source="jellyfin",
        )
    
    def _build_favorites_section(
        self,
        results: dict[str, Any],
        library_mbids: set[str],
    ) -> HomeSection | None:
        favorites = results.get("jf_favorites")
        if not favorites:
            return None
        
        return HomeSection(
            title="Your Favorites",
            type="artists",
            items=[a for a in (self._jf_item_to_artist(f, library_mbids) for f in favorites[:15]) if a is not None],
            source="jellyfin",
        )
    
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
    
    async def get_genre_artists(
        self,
        genre: str,
        limit: int = 100,
        artist_offset: int = 0,
        album_offset: int = 0,
    ) -> GenreDetailResponse:
        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}
        library_albums = await self._lidarr_repo.get_library()
        library_album_mbids = {a.musicbrainz_id.lower() for a in library_albums if a.musicbrainz_id}
        
        library_section = None
        if self._library_cache:
            lib_artists_data = await self._library_cache.get_artists_by_genre(genre, limit=50)
            lib_albums_data = await self._library_cache.get_albums_by_genre(genre, limit=50)
            
            lib_artists = [
                HomeArtist(
                    mbid=a.get("mbid"),
                    name=a.get("name", "Unknown"),
                    image_url=None,
                    listen_count=a.get("album_count"),
                    in_library=True,
                )
                for a in lib_artists_data
            ]
            
            lib_albums = [
                HomeAlbum(
                    mbid=a.get("mbid"),
                    name=a.get("title", "Unknown"),
                    artist_name=a.get("artist_name"),
                    artist_mbid=a.get("artist_mbid"),
                    image_url=a.get("cover_url"),
                    release_date=str(a.get("year")) if a.get("year") else None,
                    in_library=True,
                )
                for a in lib_albums_data
            ]
            
            library_section = GenreLibrarySection(
                artists=lib_artists,
                albums=lib_albums,
                artist_count=len(lib_artists_data),
                album_count=len(lib_albums_data),
            )
        
        mb_artist_results = await self._mb_repo.search_artists_by_tag(
            tag=genre, limit=limit, offset=artist_offset
        )
        mb_album_results = await self._mb_repo.search_release_groups_by_tag(
            tag=genre, limit=limit, offset=album_offset
        )
        
        popular_artists = [
            HomeArtist(
                mbid=result.musicbrainz_id,
                name=result.title,
                image_url=None,
                listen_count=None,
                in_library=result.musicbrainz_id.lower() in library_mbids,
            )
            for result in mb_artist_results
        ]
        
        popular_albums = [
            HomeAlbum(
                mbid=result.musicbrainz_id,
                name=result.title,
                artist_name=result.artist,
                artist_mbid=None,
                image_url=None,
                release_date=str(result.year) if result.year else None,
                in_library=result.musicbrainz_id.lower() in library_album_mbids,
            )
            for result in mb_album_results
        ]
        
        popular_section = GenrePopularSection(
            artists=popular_artists,
            albums=popular_albums,
            has_more_artists=len(mb_artist_results) >= limit,
            has_more_albums=len(mb_album_results) >= limit,
        )
        
        return GenreDetailResponse(
            genre=genre,
            library=library_section,
            popular=popular_section,
            artists=popular_artists,
            total_count=len(popular_artists),
        )

    def _get_range_label(self, range_key: str) -> str:
        labels = {
            "this_week": "This Week",
            "this_month": "This Month",
            "this_year": "This Year",
            "all_time": "All Time",
            "week": "This Week",
            "month": "This Month",
            "year": "This Year",
        }
        return labels.get(range_key, range_key.replace("_", " ").title())

    async def get_trending_artists(self, limit: int = 10) -> TrendingArtistsResponse:
        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}

        ranges = ["this_week", "this_month", "this_year", "all_time"]
        tasks = {
            r: self._lb_repo.get_sitewide_top_artists(range_=r, count=limit + 1)
            for r in ranges
        }
        results = await self._execute_tasks(tasks)

        response_data = {}
        for r in ranges:
            lb_artists = results.get(r) or []
            artists = [
                a for a in (self._lb_artist_to_home(artist, library_mbids) for artist in lb_artists) if a is not None
            ]
            featured = artists[0] if artists else None
            items = artists[1:limit] if len(artists) > 1 else []

            response_data[r] = TrendingTimeRange(
                range_key=r,
                label=self._get_range_label(r),
                featured=featured,
                items=items,
                total_count=len(artists),
            )

        return TrendingArtistsResponse(
            this_week=response_data["this_week"],
            this_month=response_data["this_month"],
            this_year=response_data["this_year"],
            all_time=response_data["all_time"],
        )

    async def get_trending_artists_by_range(
        self,
        range_key: str = "this_week",
        limit: int = 25,
        offset: int = 0,
    ) -> TrendingArtistsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"

        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}

        lb_artists = await self._lb_repo.get_sitewide_top_artists(
            range_=range_key, count=limit + 1, offset=offset
        )
        artists = [a for a in (self._lb_artist_to_home(artist, library_mbids) for artist in lb_artists) if a is not None]
        has_more = len(artists) > limit
        items = artists[:limit]

        return TrendingArtistsRangeResponse(
            range_key=range_key,
            label=self._get_range_label(range_key),
            items=items,
            offset=offset,
            limit=limit,
            has_more=has_more,
        )

    async def get_popular_albums(self, limit: int = 10) -> PopularAlbumsResponse:
        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {
            (a.musicbrainz_id or "").lower()
            for a in library_albums
            if a.musicbrainz_id
        }

        ranges = ["this_week", "this_month", "this_year", "all_time"]
        tasks = {
            r: self._lb_repo.get_sitewide_top_release_groups(range_=r, count=limit + 1)
            for r in ranges
        }
        results = await self._execute_tasks(tasks)

        response_data = {}
        for r in ranges:
            lb_albums = results.get(r) or []
            albums = [self._lb_release_to_home(a, library_mbids) for a in lb_albums]
            featured = albums[0] if albums else None
            items = albums[1:limit] if len(albums) > 1 else []

            response_data[r] = PopularTimeRange(
                range_key=r,
                label=self._get_range_label(r),
                featured=featured,
                items=items,
                total_count=len(albums),
            )

        return PopularAlbumsResponse(
            this_week=response_data["this_week"],
            this_month=response_data["this_month"],
            this_year=response_data["this_year"],
            all_time=response_data["all_time"],
        )

    async def get_popular_albums_by_range(
        self,
        range_key: str = "this_week",
        limit: int = 25,
        offset: int = 0,
    ) -> PopularAlbumsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"

        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {
            (a.musicbrainz_id or "").lower()
            for a in library_albums
            if a.musicbrainz_id
        }

        lb_albums = await self._lb_repo.get_sitewide_top_release_groups(
            range_=range_key, count=limit + 1, offset=offset
        )
        albums = [self._lb_release_to_home(a, library_mbids) for a in lb_albums]
        has_more = len(albums) > limit
        items = albums[:limit]

        return PopularAlbumsRangeResponse(
            range_key=range_key,
            label=self._get_range_label(range_key),
            items=items,
            offset=offset,
            limit=limit,
            has_more=has_more,
        )

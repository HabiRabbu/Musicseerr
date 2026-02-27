import asyncio
import logging
from typing import Any
from api.v1.schemas.home import (
    HomeArtist,
    HomeAlbum,
    GenreDetailResponse,
    GenreLibrarySection,
    GenrePopularSection,
    TrendingArtistsResponse,
    TrendingTimeRange,
    TrendingArtistsRangeResponse,
    PopularAlbumsResponse,
    PopularTimeRange,
    PopularAlbumsRangeResponse,
)
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from services.home_transformers import HomeDataTransformers
from services.preferences_service import PreferencesService
from infrastructure.cache.persistent_cache import LibraryCache

logger = logging.getLogger(__name__)


class HomeChartsService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        library_cache: LibraryCache | None = None,
        lastfm_repo: LastFmRepositoryProtocol | None = None,
        preferences_service: PreferencesService | None = None,
    ):
        self._lb_repo = listenbrainz_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._library_cache = library_cache
        self._lfm_repo = lastfm_repo
        self._preferences = preferences_service
        self._transformers = HomeDataTransformers()

    def _resolve_source(self, source: str | None) -> str:
        if source in ("listenbrainz", "lastfm"):
            resolved = source
        elif self._preferences:
            resolved = self._preferences.get_primary_music_source().source
        else:
            resolved = "listenbrainz"
        if self._preferences:
            lb_enabled = (
                self._preferences.get_listenbrainz_connection().enabled
                and bool(self._preferences.get_listenbrainz_connection().username)
            )
            lfm_enabled = self._preferences.is_lastfm_enabled()
            if resolved == "listenbrainz" and not lb_enabled and lfm_enabled:
                return "lastfm"
            if resolved == "lastfm" and not lfm_enabled and lb_enabled:
                return "listenbrainz"
        return resolved

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

    async def get_genre_artists(
        self, genre: str, limit: int = 100, artist_offset: int = 0, album_offset: int = 0
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

    async def get_trending_artists(self, limit: int = 10, source: str | None = None) -> TrendingArtistsResponse:
        resolved = self._resolve_source(source)
        if resolved == "lastfm" and self._lfm_repo:
            return await self._get_trending_artists_lastfm(limit)

        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}
        ranges = ["this_week", "this_month", "this_year", "all_time"]
        tasks = {r: self._lb_repo.get_sitewide_top_artists(range_=r, count=limit + 1) for r in ranges}
        results = await self._execute_tasks(tasks)
        response_data = {}
        for r in ranges:
            lb_artists = results.get(r) or []
            artists = [
                a for a in (self._transformers.lb_artist_to_home(artist, library_mbids) for artist in lb_artists)
                if a is not None
            ]
            featured = artists[0] if artists else None
            items = artists[1:limit] if len(artists) > 1 else []
            response_data[r] = TrendingTimeRange(
                range_key=r,
                label=HomeDataTransformers.get_range_label(r),
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
        source: str | None = None,
    ) -> TrendingArtistsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"
        resolved = self._resolve_source(source)
        if resolved == "lastfm" and self._lfm_repo:
            return await self._get_trending_artists_lastfm_range(
                range_key=range_key,
                limit=limit,
                offset=offset,
            )
        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}
        lb_artists = await self._lb_repo.get_sitewide_top_artists(
            range_=range_key, count=limit + 1, offset=offset
        )
        artists = [
            a for a in (self._transformers.lb_artist_to_home(artist, library_mbids) for artist in lb_artists)
            if a is not None
        ]
        has_more = len(artists) > limit
        items = artists[:limit]
        return TrendingArtistsRangeResponse(
            range_key=range_key,
            label=HomeDataTransformers.get_range_label(range_key),
            items=items,
            offset=offset,
            limit=limit,
            has_more=has_more,
        )

    async def get_popular_albums(self, limit: int = 10, source: str | None = None) -> PopularAlbumsResponse:
        resolved = self._resolve_source(source)
        if resolved == "lastfm" and self._lfm_repo:
            return await self._get_popular_albums_lastfm(limit)

        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {(a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id}
        ranges = ["this_week", "this_month", "this_year", "all_time"]
        tasks = {r: self._lb_repo.get_sitewide_top_release_groups(range_=r, count=limit + 1) for r in ranges}
        results = await self._execute_tasks(tasks)
        response_data = {}
        for r in ranges:
            lb_albums = results.get(r) or []
            albums = [self._transformers.lb_release_to_home(a, library_mbids) for a in lb_albums]
            featured = albums[0] if albums else None
            items = albums[1:limit] if len(albums) > 1 else []
            response_data[r] = PopularTimeRange(
                range_key=r,
                label=HomeDataTransformers.get_range_label(r),
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
        source: str | None = None,
    ) -> PopularAlbumsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"
        resolved = self._resolve_source(source)
        if resolved == "lastfm" and self._lfm_repo:
            return await self._get_popular_albums_lastfm_range(
                range_key=range_key,
                limit=limit,
                offset=offset,
            )
        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {(a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id}
        lb_albums = await self._lb_repo.get_sitewide_top_release_groups(
            range_=range_key, count=limit + 1, offset=offset
        )
        albums = [self._transformers.lb_release_to_home(a, library_mbids) for a in lb_albums]
        has_more = len(albums) > limit
        items = albums[:limit]
        return PopularAlbumsRangeResponse(
            range_key=range_key,
            label=HomeDataTransformers.get_range_label(range_key),
            items=items,
            offset=offset,
            limit=limit,
            has_more=has_more,
        )

    async def _get_trending_artists_lastfm(self, limit: int = 10) -> TrendingArtistsResponse:
        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}
        lfm_artists = await self._lfm_repo.get_global_top_artists(limit=limit + 1)
        artists = [
            a
            for a in (
                self._transformers.lastfm_artist_to_home(artist, library_mbids)
                for artist in lfm_artists
            )
            if a is not None
        ]
        featured = artists[0] if artists else None
        items = artists[1:limit] if len(artists) > 1 else []
        single_range = TrendingTimeRange(
            range_key="all_time",
            label="Global",
            featured=featured,
            items=items,
            total_count=len(artists),
        )
        return TrendingArtistsResponse(
            this_week=single_range,
            this_month=single_range,
            this_year=single_range,
            all_time=single_range,
        )

    async def _get_popular_albums_lastfm(self, limit: int = 10) -> PopularAlbumsResponse:
        ranges = ["this_week", "this_month", "this_year", "all_time"]
        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {
            (a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id
        }
        lfm_username = self._get_lastfm_username()
        if lfm_username:
            tasks = {
                range_key: self._lfm_repo.get_user_top_albums(
                    lfm_username,
                    period=self._lastfm_period_for_range(range_key),
                    limit=limit + 1,
                )
                for range_key in ranges
            }
            results = await self._execute_tasks(tasks)
        else:
            logger.warning("No Last.fm username configured; returning empty popular albums")
            empty_range = PopularTimeRange(
                range_key="all_time",
                label="Global",
                featured=None,
                items=[],
                total_count=0,
            )
            return PopularAlbumsResponse(
                this_week=empty_range,
                this_month=empty_range,
                this_year=empty_range,
                all_time=empty_range,
            )
        response_data: dict[str, PopularTimeRange] = {}
        for range_key in ranges:
            lfm_albums = results.get(range_key) or []
            albums = [
                HomeAlbum(
                    mbid=None,
                    name=album.name,
                    artist_name=album.artist_name,
                    artist_mbid=None,
                    image_url=album.image_url or None,
                    listen_count=album.playcount,
                    in_library=(album.mbid or "").lower() in library_mbids if album.mbid else False,
                    source="lastfm",
                )
                for album in lfm_albums
            ]
            response_data[range_key] = PopularTimeRange(
                range_key=range_key,
                label=HomeDataTransformers.get_range_label(range_key),
                featured=albums[0] if albums else None,
                items=albums[1:limit] if len(albums) > 1 else [],
                total_count=len(albums),
            )

        return PopularAlbumsResponse(
            this_week=response_data["this_week"],
            this_month=response_data["this_month"],
            this_year=response_data["this_year"],
            all_time=response_data["all_time"],
        )

    async def _get_trending_artists_lastfm_range(
        self, range_key: str = "this_week", limit: int = 25, offset: int = 0
    ) -> TrendingArtistsRangeResponse:
        total_to_fetch = min(limit + offset + 1, 200)
        lfm_artists = await self._lfm_repo.get_global_top_artists(limit=total_to_fetch)
        library_artists = await self._lidarr_repo.get_artists_from_library()
        library_mbids = {a.get("mbid", "").lower() for a in library_artists if a.get("mbid")}
        artists = [
            a
            for a in (
                self._transformers.lastfm_artist_to_home(artist, library_mbids)
                for artist in lfm_artists
            )
            if a is not None
        ]
        start = min(offset, len(artists))
        end = start + limit
        return TrendingArtistsRangeResponse(
            range_key=range_key,
            label=HomeDataTransformers.get_range_label(range_key),
            items=artists[start:end],
            offset=offset,
            limit=limit,
            has_more=end < len(artists),
        )

    async def _get_popular_albums_lastfm_range(
        self, range_key: str = "this_week", limit: int = 25, offset: int = 0
    ) -> PopularAlbumsRangeResponse:
        lfm_username = self._get_lastfm_username()
        if not lfm_username:
            return PopularAlbumsRangeResponse(
                range_key=range_key,
                label=HomeDataTransformers.get_range_label(range_key),
                items=[],
                offset=offset,
                limit=limit,
                has_more=False,
            )

        total_to_fetch = min(limit + offset + 1, 200)
        lfm_albums = await self._lfm_repo.get_user_top_albums(
            lfm_username,
            period=self._lastfm_period_for_range(range_key),
            limit=total_to_fetch,
        )
        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {
            (a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id
        }
        albums = [
            HomeAlbum(
                mbid=album.mbid,
                name=album.name,
                artist_name=album.artist_name,
                artist_mbid=None,
                image_url=album.image_url or None,
                listen_count=album.playcount,
                in_library=(album.mbid or "").lower() in library_mbids if album.mbid else False,
                source="lastfm",
            )
            for album in lfm_albums
        ]
        start = min(offset, len(albums))
        end = start + limit
        return PopularAlbumsRangeResponse(
            range_key=range_key,
            label=HomeDataTransformers.get_range_label(range_key),
            items=albums[start:end],
            offset=offset,
            limit=limit,
            has_more=end < len(albums),
        )

    def _get_lastfm_username(self) -> str | None:
        if not self._preferences:
            return None
        lf_settings = self._preferences.get_lastfm_connection()
        if lf_settings.enabled and lf_settings.username:
            return lf_settings.username
        return None

    def _get_lb_username(self) -> str | None:
        if not self._preferences:
            return None
        lb_settings = self._preferences.get_listenbrainz_connection()
        if lb_settings.enabled and lb_settings.username:
            return lb_settings.username
        return None

    async def get_your_top_albums(
        self, limit: int = 10, source: str | None = None
    ) -> PopularAlbumsResponse:
        resolved = self._resolve_source(source)
        if resolved == "lastfm" and self._lfm_repo:
            return await self._get_popular_albums_lastfm(limit)

        lb_username = self._get_lb_username()
        if not lb_username:
            empty = PopularTimeRange(
                range_key="all_time", label="All Time", featured=None, items=[], total_count=0
            )
            return PopularAlbumsResponse(
                this_week=empty, this_month=empty, this_year=empty, all_time=empty
            )

        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {
            (a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id
        }
        ranges = ["this_week", "this_month", "this_year", "all_time"]
        tasks = {
            r: self._lb_repo.get_user_top_release_groups(
                username=lb_username, range_=r, count=limit + 1
            )
            for r in ranges
        }
        results = await self._execute_tasks(tasks)
        response_data: dict[str, PopularTimeRange] = {}
        for r in ranges:
            rgs = results.get(r) or []
            albums = [self._transformers.lb_release_to_home(rg, library_mbids) for rg in rgs]
            response_data[r] = PopularTimeRange(
                range_key=r,
                label=HomeDataTransformers.get_range_label(r),
                featured=albums[0] if albums else None,
                items=albums[1:limit] if len(albums) > 1 else [],
                total_count=len(albums),
            )
        return PopularAlbumsResponse(
            this_week=response_data["this_week"],
            this_month=response_data["this_month"],
            this_year=response_data["this_year"],
            all_time=response_data["all_time"],
        )

    async def get_your_top_albums_by_range(
        self,
        range_key: str = "this_week",
        limit: int = 25,
        offset: int = 0,
        source: str | None = None,
    ) -> PopularAlbumsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"
        resolved = self._resolve_source(source)
        if resolved == "lastfm" and self._lfm_repo:
            return await self._get_popular_albums_lastfm_range(
                range_key=range_key, limit=limit, offset=offset
            )

        lb_username = self._get_lb_username()
        if not lb_username:
            return PopularAlbumsRangeResponse(
                range_key=range_key,
                label=HomeDataTransformers.get_range_label(range_key),
                items=[],
                offset=offset,
                limit=limit,
                has_more=False,
            )

        library_albums = await self._lidarr_repo.get_library()
        library_mbids = {
            (a.musicbrainz_id or "").lower() for a in library_albums if a.musicbrainz_id
        }
        rgs = await self._lb_repo.get_user_top_release_groups(
            username=lb_username, range_=range_key, count=limit + 1, offset=offset
        )
        albums = [self._transformers.lb_release_to_home(rg, library_mbids) for rg in rgs]
        has_more = len(albums) > limit
        items = albums[:limit]
        return PopularAlbumsRangeResponse(
            range_key=range_key,
            label=HomeDataTransformers.get_range_label(range_key),
            items=items,
            offset=offset,
            limit=limit,
            has_more=has_more,
        )

    @staticmethod
    def _lastfm_period_for_range(range_key: str) -> str:
        mapping = {
            "this_week": "7day",
            "this_month": "1month",
            "this_year": "12month",
            "all_time": "overall",
        }
        return mapping.get(range_key, "1month")

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
)
from services.home_transformers import HomeDataTransformers
from infrastructure.cache.persistent_cache import LibraryCache

logger = logging.getLogger(__name__)


class HomeChartsService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        library_cache: LibraryCache | None = None,
    ):
        self._lb_repo = listenbrainz_repo
        self._lidarr_repo = lidarr_repo
        self._mb_repo = musicbrainz_repo
        self._library_cache = library_cache
        self._transformers = HomeDataTransformers()

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

    async def get_trending_artists(self, limit: int = 10) -> TrendingArtistsResponse:
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
        self, range_key: str = "this_week", limit: int = 25, offset: int = 0
    ) -> TrendingArtistsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"
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

    async def get_popular_albums(self, limit: int = 10) -> PopularAlbumsResponse:
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
        self, range_key: str = "this_week", limit: int = 25, offset: int = 0
    ) -> PopularAlbumsRangeResponse:
        allowed_ranges = ["this_week", "this_month", "this_year", "all_time"]
        if range_key not in allowed_ranges:
            range_key = "this_week"
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

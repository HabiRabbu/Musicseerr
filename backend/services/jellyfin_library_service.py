import asyncio

from api.v1.schemas.jellyfin import (
    JellyfinAlbumDetail,
    JellyfinAlbumMatch,
    JellyfinAlbumSummary,
    JellyfinArtistSummary,
    JellyfinLibraryStats,
    JellyfinSearchResponse,
    JellyfinTrackInfo,
)
from infrastructure.cover_urls import prefer_artist_cover_url, prefer_release_group_cover_url
from repositories.protocols import JellyfinRepositoryProtocol
from repositories.jellyfin_models import JellyfinItem
from services.preferences_service import PreferencesService


class JellyfinLibraryService:
    _DEFAULT_RECENTLY_PLAYED_TTL = 300
    _DEFAULT_FAVORITES_TTL = 300
    _DEFAULT_GENRES_TTL = 3600
    _DEFAULT_STATS_TTL = 600

    def __init__(
        self,
        jellyfin_repo: JellyfinRepositoryProtocol,
        preferences_service: PreferencesService,
    ):
        self._jellyfin = jellyfin_repo
        self._preferences = preferences_service

    def _get_recently_played_ttl(self) -> int:
        try:
            return self._preferences.get_advanced_settings().cache_ttl_jellyfin_recently_played
        except Exception:  # noqa: BLE001
            return self._DEFAULT_RECENTLY_PLAYED_TTL

    def _get_favorites_ttl(self) -> int:
        try:
            return self._preferences.get_advanced_settings().cache_ttl_jellyfin_favorites
        except Exception:  # noqa: BLE001
            return self._DEFAULT_FAVORITES_TTL

    def _get_genres_ttl(self) -> int:
        try:
            return self._preferences.get_advanced_settings().cache_ttl_jellyfin_genres
        except Exception:  # noqa: BLE001
            return self._DEFAULT_GENRES_TTL

    def _get_stats_ttl(self) -> int:
        try:
            return self._preferences.get_advanced_settings().cache_ttl_jellyfin_library_stats
        except Exception:  # noqa: BLE001
            return self._DEFAULT_STATS_TTL

    def _item_to_album_summary(self, item: JellyfinItem) -> JellyfinAlbumSummary:
        pids = item.provider_ids or {}
        mbid = pids.get("MusicBrainzReleaseGroup") or pids.get("MusicBrainzAlbum")
        artist_mbid = pids.get("MusicBrainzAlbumArtist") or pids.get("MusicBrainzArtist")
        image_url = prefer_release_group_cover_url(
            mbid,
            self._jellyfin.get_image_url(item.id, item.image_tag),
            size=500,
        )
        return JellyfinAlbumSummary(
            jellyfin_id=item.id,
            name=item.name,
            artist_name=item.artist_name or "",
            year=item.year,
            track_count=item.child_count or 0,
            image_url=image_url,
            musicbrainz_id=mbid,
            artist_musicbrainz_id=artist_mbid,
        )

    def _item_to_track_info(self, item: JellyfinItem) -> JellyfinTrackInfo:
        duration_seconds = (item.duration_ticks / 10_000_000.0) if item.duration_ticks else 0.0
        return JellyfinTrackInfo(
            jellyfin_id=item.id,
            title=item.name,
            track_number=item.index_number or 0,
            disc_number=item.parent_index_number or 1,
            duration_seconds=duration_seconds,
            album_name=item.album_name or "",
            artist_name=item.artist_name or "",
            codec=item.codec,
            bitrate=item.bitrate,
        )

    @staticmethod
    def _fix_missing_track_numbers(tracks: list[JellyfinTrackInfo]) -> list[JellyfinTrackInfo]:
        """When all tracks share the same track_number (e.g. Jellyfin returns 0
        for every track), assign 1-based indices so downstream Map lookups work."""
        if len(tracks) <= 1:
            return tracks
        tracks_by_disc: dict[int, list[JellyfinTrackInfo]] = {}
        for track in tracks:
            tracks_by_disc.setdefault(track.disc_number, []).append(track)

        renumbered_ids: dict[str, int] = {}
        for disc_tracks in tracks_by_disc.values():
            numbers = {t.track_number for t in disc_tracks}
            if len(numbers) > 1:
                continue
            for i, track in enumerate(disc_tracks, start=1):
                renumbered_ids[track.jellyfin_id] = i

        fixed: list[JellyfinTrackInfo] = []
        for track in tracks:
            track_number = renumbered_ids.get(track.jellyfin_id, track.track_number)
            fixed.append(JellyfinTrackInfo(
                jellyfin_id=track.jellyfin_id,
                title=track.title,
                track_number=track_number,
                disc_number=track.disc_number,
                duration_seconds=track.duration_seconds,
                album_name=track.album_name,
                artist_name=track.artist_name,
                codec=track.codec,
                bitrate=track.bitrate,
            ))
        return fixed

    async def get_albums(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        sort_order: str = "Ascending",
        genre: str | None = None,
    ) -> tuple[list[JellyfinAlbumSummary], int]:
        items, total = await self._jellyfin.get_albums(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, genre=genre
        )
        return [self._item_to_album_summary(i) for i in items], total

    async def get_album_detail(self, album_id: str) -> JellyfinAlbumDetail | None:
        item = await self._jellyfin.get_album_detail(album_id)
        if not item:
            return None

        tracks_items = await self._jellyfin.get_album_tracks(album_id)
        tracks = self._fix_missing_track_numbers(
            [self._item_to_track_info(t) for t in tracks_items]
        )
        pids = item.provider_ids or {}
        mbid = pids.get("MusicBrainzReleaseGroup") or pids.get("MusicBrainzAlbum")
        artist_mbid = pids.get("MusicBrainzAlbumArtist") or pids.get("MusicBrainzArtist")
        image_url = prefer_release_group_cover_url(
            mbid,
            self._jellyfin.get_image_url(item.id, item.image_tag),
            size=500,
        )

        return JellyfinAlbumDetail(
            jellyfin_id=item.id,
            name=item.name,
            artist_name=item.artist_name or "",
            year=item.year,
            track_count=len(tracks),
            image_url=image_url,
            musicbrainz_id=mbid,
            artist_musicbrainz_id=artist_mbid,
            tracks=tracks,
        )

    async def get_album_tracks(self, album_id: str) -> list[JellyfinTrackInfo]:
        items = await self._jellyfin.get_album_tracks(album_id)
        return self._fix_missing_track_numbers(
            [self._item_to_track_info(i) for i in items]
        )

    async def match_album_by_mbid(self, musicbrainz_id: str) -> JellyfinAlbumMatch:
        item = await self._jellyfin.get_album_by_mbid(musicbrainz_id)
        if not item:
            return JellyfinAlbumMatch(found=False)

        tracks_items = await self._jellyfin.get_album_tracks(item.id)
        tracks = self._fix_missing_track_numbers(
            [self._item_to_track_info(t) for t in tracks_items]
        )

        return JellyfinAlbumMatch(
            found=True,
            jellyfin_album_id=item.id,
            tracks=tracks,
        )

    async def get_artists(
        self, limit: int = 50, offset: int = 0
    ) -> list[JellyfinArtistSummary]:
        items = await self._jellyfin.get_artists(limit=limit, offset=offset)
        artists = []
        for item in items:
            mbid = item.provider_ids.get("MusicBrainzArtist") if item.provider_ids else None
            image_url = prefer_artist_cover_url(
                mbid,
                self._jellyfin.get_image_url(item.id, item.image_tag),
                size=500,
            )
            artists.append(JellyfinArtistSummary(
                jellyfin_id=item.id,
                name=item.name,
                image_url=image_url,
                album_count=item.album_count or 0,
                musicbrainz_id=mbid,
            ))
        return artists

    async def search(
        self, query: str
    ) -> JellyfinSearchResponse:
        items = await self._jellyfin.search_items(query)
        albums = []
        artists = []
        tracks = []
        for item in items:
            if item.type == "MusicAlbum":
                albums.append(self._item_to_album_summary(item))
            elif item.type in ("MusicArtist", "Artist"):
                mbid = item.provider_ids.get("MusicBrainzArtist") if item.provider_ids else None
                image_url = prefer_artist_cover_url(
                    mbid,
                    self._jellyfin.get_image_url(item.id, item.image_tag),
                    size=500,
                )
                artists.append(JellyfinArtistSummary(
                    jellyfin_id=item.id,
                    name=item.name,
                    image_url=image_url,
                    musicbrainz_id=mbid,
                ))
            elif item.type == "Audio":
                tracks.append(self._item_to_track_info(item))
        return JellyfinSearchResponse(albums=albums, artists=artists, tracks=tracks)

    async def get_recently_played(self, limit: int = 20) -> list[JellyfinAlbumSummary]:
        ttl_seconds = self._get_recently_played_ttl()
        items = await self._jellyfin.get_recently_played(
            limit=limit,
            ttl_seconds=ttl_seconds,
        )
        seen_album_ids: set[str] = set()
        unique_album_ids: list[str] = []
        for item in items:
            aid = item.album_id or item.parent_id
            if not aid or aid in seen_album_ids:
                continue
            seen_album_ids.add(aid)
            unique_album_ids.append(aid)
            if len(unique_album_ids) >= limit:
                break

        _CONCURRENCY_LIMIT = 5
        sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

        async def _fetch(aid: str) -> JellyfinItem | None:
            async with sem:
                return await self._jellyfin.get_album_detail(aid)

        details = await asyncio.gather(
            *(_fetch(aid) for aid in unique_album_ids)
        )
        return [
            self._item_to_album_summary(detail)
            for detail in details
            if detail is not None
        ]

    async def get_favorites(self, limit: int = 20) -> list[JellyfinAlbumSummary]:
        ttl_seconds = self._get_favorites_ttl()
        items = await self._jellyfin.get_favorite_albums(
            limit=limit,
            ttl_seconds=ttl_seconds,
        )
        return [self._item_to_album_summary(i) for i in items]

    async def get_genres(self) -> list[str]:
        ttl_seconds = self._get_genres_ttl()
        return await self._jellyfin.get_genres(ttl_seconds=ttl_seconds)

    async def get_stats(self) -> JellyfinLibraryStats:
        ttl_seconds = self._get_stats_ttl()
        raw = await self._jellyfin.get_library_stats(ttl_seconds=ttl_seconds)
        return JellyfinLibraryStats(
            total_tracks=raw.get("total_tracks", 0),
            total_albums=raw.get("total_albums", 0),
            total_artists=raw.get("total_artists", 0),
        )

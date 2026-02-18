import asyncio
import logging

from api.v1.schemas.jellyfin import (
    JellyfinAlbumDetail,
    JellyfinAlbumMatch,
    JellyfinAlbumSummary,
    JellyfinArtistSummary,
    JellyfinLibraryStats,
    JellyfinSearchResponse,
    JellyfinTrackInfo,
)
from repositories.jellyfin_repository import JellyfinRepository
from repositories.jellyfin_models import JellyfinItem

logger = logging.getLogger(__name__)


class JellyfinLibraryService:
    def __init__(self, jellyfin_repo: JellyfinRepository):
        self._jellyfin = jellyfin_repo

    def _item_to_album_summary(self, item: JellyfinItem) -> JellyfinAlbumSummary:
        pids = item.provider_ids or {}
        mbid = pids.get("MusicBrainzReleaseGroup") or pids.get("MusicBrainzAlbum")
        artist_mbid = pids.get("MusicBrainzAlbumArtist") or pids.get("MusicBrainzArtist")
        return JellyfinAlbumSummary(
            jellyfin_id=item.id,
            name=item.name,
            artist_name=item.artist_name or "",
            year=item.year,
            track_count=item.child_count or 0,
            image_url=self._jellyfin.get_image_url(item.id, item.image_tag),
            musicbrainz_id=mbid,
            artist_musicbrainz_id=artist_mbid,
        )

    def _item_to_track_info(self, item: JellyfinItem) -> JellyfinTrackInfo:
        duration_seconds = (item.duration_ticks / 10_000_000.0) if item.duration_ticks else 0.0
        return JellyfinTrackInfo(
            jellyfin_id=item.id,
            title=item.name,
            track_number=item.index_number or 0,
            duration_seconds=duration_seconds,
            album_name=item.album_name or "",
            artist_name=item.artist_name or "",
            codec=item.codec,
            bitrate=item.bitrate,
        )

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
        tracks = [self._item_to_track_info(t) for t in tracks_items]
        pids = item.provider_ids or {}
        mbid = pids.get("MusicBrainzReleaseGroup") or pids.get("MusicBrainzAlbum")
        artist_mbid = pids.get("MusicBrainzAlbumArtist") or pids.get("MusicBrainzArtist")

        return JellyfinAlbumDetail(
            jellyfin_id=item.id,
            name=item.name,
            artist_name=item.artist_name or "",
            year=item.year,
            track_count=len(tracks),
            image_url=self._jellyfin.get_image_url(item.id, item.image_tag),
            musicbrainz_id=mbid,
            artist_musicbrainz_id=artist_mbid,
            tracks=tracks,
        )

    async def get_album_tracks(self, album_id: str) -> list[JellyfinTrackInfo]:
        items = await self._jellyfin.get_album_tracks(album_id)
        return [self._item_to_track_info(i) for i in items]

    async def match_album_by_mbid(self, musicbrainz_id: str) -> JellyfinAlbumMatch:
        item = await self._jellyfin.get_album_by_mbid(musicbrainz_id)
        if not item:
            return JellyfinAlbumMatch(found=False)

        tracks_items = await self._jellyfin.get_album_tracks(item.id)
        tracks = [self._item_to_track_info(t) for t in tracks_items]

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
            artists.append(JellyfinArtistSummary(
                jellyfin_id=item.id,
                name=item.name,
                image_url=self._jellyfin.get_image_url(item.id, item.image_tag),
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
                artists.append(JellyfinArtistSummary(
                    jellyfin_id=item.id,
                    name=item.name,
                    image_url=self._jellyfin.get_image_url(item.id, item.image_tag),
                    musicbrainz_id=mbid,
                ))
            elif item.type == "Audio":
                tracks.append(self._item_to_track_info(item))
        return JellyfinSearchResponse(albums=albums, artists=artists, tracks=tracks)

    async def get_recently_played(self, limit: int = 20) -> list[JellyfinAlbumSummary]:
        items = await self._jellyfin.get_recently_played(limit=limit)
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
        items = await self._jellyfin.get_favorite_albums(limit=limit)
        return [self._item_to_album_summary(i) for i in items]

    async def get_genres(self) -> list[str]:
        return await self._jellyfin.get_genres()

    async def get_stats(self) -> JellyfinLibraryStats:
        raw = await self._jellyfin.get_library_stats()
        return JellyfinLibraryStats(
            total_tracks=raw.get("total_tracks", 0),
            total_albums=raw.get("total_albums", 0),
            total_artists=raw.get("total_artists", 0),
        )

from __future__ import annotations

import asyncio
import logging
import time
import unicodedata
import re
from typing import TYPE_CHECKING

from api.v1.schemas.navidrome import (
    NavidromeAlbumDetail,
    NavidromeAlbumMatch,
    NavidromeAlbumSummary,
    NavidromeArtistSummary,
    NavidromeLibraryStats,
    NavidromeSearchResponse,
    NavidromeTrackInfo,
)
from infrastructure.cover_urls import prefer_artist_cover_url, prefer_release_group_cover_url
from repositories.navidrome_models import SubsonicAlbum, SubsonicSong
from repositories.protocols import NavidromeRepositoryProtocol
from services.preferences_service import PreferencesService

if TYPE_CHECKING:
    from infrastructure.persistence import LibraryDB, MBIDStore

logger = logging.getLogger(__name__)

_CONCURRENCY_LIMIT = 5
_NEGATIVE_CACHE_TTL = 14400  # 4 hours - aligned with periodic warmup interval


def _cache_get_mbid(cache: dict[str, str | tuple[None, float]], key: str) -> str | None:
    """Extract MBID from cache, returning None for negative or missing entries."""
    val = cache.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return val
    return None


def _clean_album_name(name: str) -> str:
    """Strip common suffixes like '(Remastered 2009)', '[Deluxe Edition]', year prefixes, etc."""
    cleaned = name.strip()
    cleaned = re.sub(r'\s*[\(\[][^)\]]*(?:remaster|deluxe|edition|bonus|expanded|mono|stereo|anniversary)[^)\]]*[\)\]]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^\d{4}\s*[-\u2013\u2014]\s*', '', cleaned)
    cleaned = re.sub(r'\s*-\s*EP$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\[[^\]]*\]\s*$', '', cleaned)
    return cleaned.strip()


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]", "", text.lower())
    return text


class NavidromeLibraryService:

    def __init__(
        self,
        navidrome_repo: NavidromeRepositoryProtocol,
        preferences_service: PreferencesService,
        library_db: 'LibraryDB | None' = None,
        mbid_store: 'MBIDStore | None' = None,
    ):
        self._navidrome = navidrome_repo
        self._preferences = preferences_service
        self._library_db = library_db
        self._mbid_store = mbid_store
        # Cache values: str (resolved MBID) or tuple (None, timestamp) for negative entries
        self._album_mbid_cache: dict[str, str | tuple[None, float]] = {}
        self._artist_mbid_cache: dict[str, str | tuple[None, float]] = {}
        self._mbid_to_navidrome_id: dict[str, str] = {}
        # Lidarr in-memory indices (populated during warmup)
        self._lidarr_album_index: dict[str, tuple[str, str]] = {}
        self._lidarr_artist_index: dict[str, str] = {}
        self._dirty = False

    def lookup_navidrome_id(self, mbid: str) -> str | None:
        """Public accessor for the MBID -> Navidrome album ID reverse index."""
        return self._mbid_to_navidrome_id.get(mbid)

    def invalidate_album_cache(self, album_mbid: str) -> None:
        """Remove cached entries for a specific album MBID, forcing re-lookup on next match."""
        self._mbid_to_navidrome_id.pop(album_mbid, None)
        stale_keys = [k for k, v in self._album_mbid_cache.items() if v == album_mbid]
        for key in stale_keys:
            del self._album_mbid_cache[key]
        if stale_keys:
            self._dirty = True

    async def _resolve_album_mbid(self, name: str, artist: str) -> str | None:
        """Resolve a release-group MBID for an album via Lidarr library matching."""
        if not name or not artist:
            return None
        cache_key = f"{_normalize(name)}:{_normalize(artist)}"
        if cache_key in self._album_mbid_cache:
            cached = self._album_mbid_cache[cache_key]
            if isinstance(cached, str):
                return cached
            if isinstance(cached, tuple):
                _, ts = cached
                if time.time() - ts < _NEGATIVE_CACHE_TTL:
                    return None
                del self._album_mbid_cache[cache_key]
            elif cached is None:
                del self._album_mbid_cache[cache_key]

        # Try exact match in Lidarr index
        match = self._lidarr_album_index.get(cache_key)
        if match:
            self._album_mbid_cache[cache_key] = match[0]
            self._dirty = True
            return match[0]

        # Try cleaned name match (strip remaster/deluxe/EP/single suffixes)
        clean_key = f"{_normalize(_clean_album_name(name))}:{_normalize(artist)}"
        if clean_key != cache_key:
            match = self._lidarr_album_index.get(clean_key)
            if match:
                self._album_mbid_cache[cache_key] = match[0]
                self._dirty = True
                return match[0]

        self._album_mbid_cache[cache_key] = (None, time.time())
        self._dirty = True
        return None

    async def _resolve_artist_mbid(self, name: str) -> str | None:
        """Resolve an artist MBID via Lidarr library matching."""
        if not name:
            return None
        cache_key = _normalize(name)
        if cache_key in self._artist_mbid_cache:
            cached = self._artist_mbid_cache[cache_key]
            if isinstance(cached, str):
                return cached
            if isinstance(cached, tuple):
                _, ts = cached
                if time.time() - ts < _NEGATIVE_CACHE_TTL:
                    return None
                del self._artist_mbid_cache[cache_key]
            elif cached is None:
                del self._artist_mbid_cache[cache_key]

        match = self._lidarr_artist_index.get(cache_key)
        if match:
            self._artist_mbid_cache[cache_key] = match
            self._dirty = True
            return match

        self._artist_mbid_cache[cache_key] = (None, time.time())
        self._dirty = True
        return None

    async def persist_if_dirty(self) -> None:
        """Persist in-memory MBID cache to SQLite if there are unsaved changes."""
        if not self._dirty or not self._mbid_store:
            return
        try:
            serializable_albums = {k: (v if isinstance(v, str) else None) for k, v in self._album_mbid_cache.items()}
            serializable_artists = {k: (v if isinstance(v, str) else None) for k, v in self._artist_mbid_cache.items()}
            await self._mbid_store.save_navidrome_album_mbid_index(serializable_albums)
            await self._mbid_store.save_navidrome_artist_mbid_index(serializable_artists)
            self._dirty = False
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist dirty Navidrome MBID cache", exc_info=True)

    async def _build_artist_summary(self, artist_data: object) -> NavidromeArtistSummary:
        """Build an artist summary, enriching MBID from Lidarr if needed."""
        name = getattr(artist_data, 'name', '')
        lidarr_mbid = await self._resolve_artist_mbid(name) if name else None
        mbid = lidarr_mbid or getattr(artist_data, 'musicBrainzId', None) or None
        image_url = prefer_artist_cover_url(mbid, None, size=500)
        return NavidromeArtistSummary(
            navidrome_id=artist_data.id,
            name=name,
            image_url=image_url,
            album_count=getattr(artist_data, 'albumCount', 0),
            musicbrainz_id=mbid,
        )

    def _song_to_track_info(self, song: SubsonicSong) -> NavidromeTrackInfo:
        return NavidromeTrackInfo(
            navidrome_id=song.id,
            title=song.title,
            track_number=song.track,
            disc_number=song.discNumber or 1,
            duration_seconds=float(song.duration),
            album_name=song.album,
            artist_name=song.artist,
            codec=song.suffix or None,
            bitrate=song.bitRate or None,
        )

    async def _album_to_summary(self, album: SubsonicAlbum) -> NavidromeAlbumSummary:
        # Only expose Lidarr-resolved MBIDs. Navidrome may return release IDs instead.
        mbid = await self._resolve_album_mbid(album.name, album.artist) if album.name and album.artist else None
        if mbid:
            self._mbid_to_navidrome_id[mbid] = album.id
        artist_mbid = await self._resolve_artist_mbid(album.artist) if album.artist else None
        fallback = f"/api/v1/navidrome/cover/{album.coverArt}" if album.coverArt else None
        image_url = prefer_release_group_cover_url(mbid, fallback, size=500)
        return NavidromeAlbumSummary(
            navidrome_id=album.id,
            name=album.name,
            artist_name=album.artist,
            year=album.year or None,
            track_count=album.songCount,
            image_url=image_url,
            musicbrainz_id=mbid,
            artist_musicbrainz_id=artist_mbid,
        )

    @staticmethod
    def _fix_missing_track_numbers(tracks: list[NavidromeTrackInfo]) -> list[NavidromeTrackInfo]:
        if len(tracks) <= 1:
            return tracks
        tracks_by_disc: dict[int, list[NavidromeTrackInfo]] = {}
        for track in tracks:
            tracks_by_disc.setdefault(track.disc_number, []).append(track)

        renumbered_ids: dict[str, int] = {}
        for disc_tracks in tracks_by_disc.values():
            numbers = {t.track_number for t in disc_tracks}
            if len(numbers) > 1:
                continue
            for i, track in enumerate(disc_tracks, start=1):
                renumbered_ids[track.navidrome_id] = i

        fixed: list[NavidromeTrackInfo] = []
        for track in tracks:
            track_number = renumbered_ids.get(track.navidrome_id, track.track_number)
            fixed.append(NavidromeTrackInfo(
                navidrome_id=track.navidrome_id,
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
        type: str = "alphabeticalByName",
        size: int = 50,
        offset: int = 0,
        genre: str | None = None,
    ) -> list[NavidromeAlbumSummary]:
        albums = await self._navidrome.get_album_list(type=type, size=size, offset=offset, genre=genre)
        filtered = [a for a in albums if a.name and a.name != "Unknown"]
        summaries = await asyncio.gather(*(self._album_to_summary(a) for a in filtered))
        return list(summaries)

    async def get_album_detail(self, album_id: str) -> NavidromeAlbumDetail | None:
        try:
            album = await self._navidrome.get_album(album_id)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch Navidrome album %s", album_id, exc_info=True)
            return None

        songs = album.song or []
        tracks = self._fix_missing_track_numbers(
            [self._song_to_track_info(s) for s in songs]
        )
        mbid = await self._resolve_album_mbid(album.name, album.artist) if album.name and album.artist else None
        artist_mbid = await self._resolve_artist_mbid(album.artist) if album.artist else None
        fallback = f"/api/v1/navidrome/cover/{album.coverArt}" if album.coverArt else None
        image_url = prefer_release_group_cover_url(mbid, fallback, size=500)

        return NavidromeAlbumDetail(
            navidrome_id=album.id,
            name=album.name,
            artist_name=album.artist,
            year=album.year or None,
            track_count=len(tracks),
            image_url=image_url,
            musicbrainz_id=mbid,
            artist_musicbrainz_id=artist_mbid,
            tracks=tracks,
        )

    async def get_artists(self) -> list[NavidromeArtistSummary]:
        artists = await self._navidrome.get_artists()
        summaries = await asyncio.gather(*(self._build_artist_summary(a) for a in artists))
        return list(summaries)

    async def get_artist_detail(self, artist_id: str) -> dict[str, object] | None:
        try:
            artist = await self._navidrome.get_artist(artist_id)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch Navidrome artist %s", artist_id, exc_info=True)
            return None

        lidarr_mbid = await self._resolve_artist_mbid(artist.name) if artist.name else None
        mbid = lidarr_mbid or artist.musicBrainzId or None
        image_url = prefer_artist_cover_url(mbid, None, size=500)

        albums: list[NavidromeAlbumSummary] = []
        sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

        async def _fetch_album(album_id: str) -> NavidromeAlbumSummary | None:
            async with sem:
                try:
                    detail = await self._navidrome.get_album(album_id)
                    return await self._album_to_summary(detail)
                except Exception:  # noqa: BLE001
                    return None

        search_result = await self._navidrome.search(artist.name, artist_count=0, album_count=500, song_count=0)
        artist_album_ids = [a.id for a in search_result.album if a.artistId == artist_id and a.name and a.name != "Unknown"]

        if artist_album_ids:
            fetched = await asyncio.gather(*(_fetch_album(aid) for aid in artist_album_ids))
            albums = [a for a in fetched if a is not None]

        return {
            "artist": NavidromeArtistSummary(
                navidrome_id=artist.id,
                name=artist.name,
                image_url=image_url,
                album_count=artist.albumCount,
                musicbrainz_id=mbid,
            ),
            "albums": albums,
        }

    async def search(self, query: str) -> NavidromeSearchResponse:
        result = await self._navidrome.search(query)
        filtered_albums = [a for a in result.album if a.name and a.name != "Unknown"]
        albums_task = asyncio.gather(*(self._album_to_summary(a) for a in filtered_albums))
        artists_task = asyncio.gather(*(self._build_artist_summary(a) for a in result.artist))
        albums, artists = await asyncio.gather(albums_task, artists_task)
        tracks = [self._song_to_track_info(s) for s in result.song]
        return NavidromeSearchResponse(albums=list(albums), artists=list(artists), tracks=tracks)

    async def get_recent(self, limit: int = 20) -> list[NavidromeAlbumSummary]:
        albums = await self._navidrome.get_album_list(type="recent", size=limit, offset=0)
        filtered = [a for a in albums if a.name and a.name != "Unknown"]
        summaries = await asyncio.gather(*(self._album_to_summary(a) for a in filtered))
        return list(summaries)

    async def get_favorites(self) -> NavidromeSearchResponse:
        starred = await self._navidrome.get_starred()
        filtered_albums = [a for a in starred.album if a.name and a.name != "Unknown"]
        albums_task = asyncio.gather(*(self._album_to_summary(a) for a in filtered_albums))
        artists_task = asyncio.gather(*(self._build_artist_summary(a) for a in starred.artist))
        albums, artists = await asyncio.gather(albums_task, artists_task)
        tracks = [self._song_to_track_info(s) for s in starred.song]
        return NavidromeSearchResponse(albums=list(albums), artists=list(artists), tracks=tracks)

    async def get_genres(self) -> list[str]:
        genres = await self._navidrome.get_genres()
        return [g.name for g in genres if g.name]

    async def get_stats(self) -> NavidromeLibraryStats:
        artists = await self._navidrome.get_artists()
        # Fetch a single album just to trigger the endpoint, then count via pagination
        first_page = await self._navidrome.get_album_list(type="alphabeticalByName", size=1, offset=0)
        total_albums = 0
        if first_page:
            # Count all albums by paginating with large pages
            all_albums = await self._navidrome.get_album_list(type="alphabeticalByName", size=500, offset=0)
            total_albums = len(all_albums)
            if total_albums >= 500:
                offset = 500
                while True:
                    batch = await self._navidrome.get_album_list(type="alphabeticalByName", size=500, offset=offset)
                    if not batch:
                        break
                    total_albums += len(batch)
                    if len(batch) < 500:
                        break
                    offset += 500
        genres = await self._navidrome.get_genres()
        total_songs = sum(g.songCount for g in genres)
        return NavidromeLibraryStats(
            total_tracks=total_songs,
            total_albums=total_albums,
            total_artists=len(artists),
        )

    async def get_album_match(
        self,
        album_id: str,
        album_name: str,
        artist_name: str,
    ) -> NavidromeAlbumMatch:
        sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

        async def _fetch_detail(aid: str) -> NavidromeAlbumDetail | None:
            async with sem:
                return await self.get_album_detail(aid)

        # Fast path: direct MBID -> navidrome_id lookup from the reverse index.
        if album_id and album_id in self._mbid_to_navidrome_id:
            nav_id = self._mbid_to_navidrome_id[album_id]
            detail = await _fetch_detail(nav_id)
            if detail:
                return NavidromeAlbumMatch(
                    found=True,
                    navidrome_album_id=detail.navidrome_id,
                    tracks=detail.tracks,
                )

        if album_id:
            search_result = await self._navidrome.search(
                album_name, artist_count=0, album_count=50, song_count=0
            )
            for candidate in search_result.album:
                if candidate.musicBrainzId and candidate.musicBrainzId == album_id:
                    detail = await _fetch_detail(candidate.id)
                    if detail:
                        return NavidromeAlbumMatch(
                            found=True,
                            navidrome_album_id=detail.navidrome_id,
                            tracks=detail.tracks,
                        )

        if album_name and artist_name:
            norm_album = _normalize(album_name)
            norm_artist = _normalize(artist_name)

            search_result = await self._navidrome.search(
                album_name, artist_count=0, album_count=50, song_count=0
            )
            for candidate in search_result.album:
                if (
                    _normalize(candidate.name) == norm_album
                    and _normalize(candidate.artist) == norm_artist
                ):
                    detail = await _fetch_detail(candidate.id)
                    if detail:
                        return NavidromeAlbumMatch(
                            found=True,
                            navidrome_album_id=detail.navidrome_id,
                            tracks=detail.tracks,
                        )

        return NavidromeAlbumMatch(found=False)

    async def warm_mbid_cache(self) -> None:
        """Background task: enrich all Navidrome albums and artists with MBIDs from Lidarr library matching.
        Loads from SQLite first for instant startup; enriches from Lidarr library matching."""

        # Phase 0: Build Lidarr indices from library cache
        if self._library_db:
            try:
                lidarr_albums = await self._library_db.get_all_albums_for_matching()
                self._lidarr_album_index = {}
                self._lidarr_artist_index = {}
                for title, artist_name, album_mbid, artist_mbid in lidarr_albums:
                    key = f"{_normalize(title)}:{_normalize(artist_name)}"
                    clean_key = f"{_normalize(_clean_album_name(title))}:{_normalize(artist_name)}"
                    self._lidarr_album_index[key] = (album_mbid, artist_mbid)
                    if clean_key != key:
                        self._lidarr_album_index[clean_key] = (album_mbid, artist_mbid)
                    norm_artist = _normalize(artist_name)
                    if norm_artist and artist_mbid:
                        self._lidarr_artist_index[norm_artist] = artist_mbid
            except Exception:  # noqa: BLE001
                logger.warning("Failed to build Lidarr matching indices", exc_info=True)

        # Phase 1: Load from persistent SQLite cache (serves requests while Lidarr may be unavailable)
        loaded_from_disk = False
        if self._mbid_store:
            try:
                disk_albums = await self._mbid_store.load_navidrome_album_mbid_index(max_age_seconds=86400)
                disk_artists = await self._mbid_store.load_navidrome_artist_mbid_index(max_age_seconds=86400)
                if disk_albums or disk_artists:
                    self._album_mbid_cache.update(disk_albums)
                    self._artist_mbid_cache.update(disk_artists)
                    loaded_from_disk = True
            except Exception:  # noqa: BLE001
                logger.warning("Failed to load Navidrome MBID cache from disk", exc_info=True)

        if not self._lidarr_album_index:
            logger.warning("Lidarr library data unavailable - Lidarr enrichment will be skipped")

        # Phase 2: Fetch current Navidrome library (paginated) for reconciliation + enrichment
        try:
            all_albums: list[SubsonicAlbum] = []
            offset = 0
            while True:
                batch = await self._navidrome.get_album_list(
                    type="alphabeticalByName", size=500, offset=offset
                )
                if not batch:
                    break
                all_albums.extend(batch)
                if len(batch) < 500:
                    break
                offset += 500
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch Navidrome albums for MBID enrichment")
            return

        # Phase 3: Reconcile - remove stale entries no longer in Navidrome
        current_album_keys: set[str] = set()
        current_artist_names: set[str] = set()
        for album in all_albums:
            if album.name and album.name != "Unknown":
                current_album_keys.add(f"{_normalize(album.name)}:{_normalize(album.artist)}")
            if album.artist:
                current_artist_names.add(album.artist)

        current_artist_keys = {_normalize(n) for n in current_artist_names}
        stale_album_keys = set(self._album_mbid_cache.keys()) - current_album_keys
        stale_artist_keys = set(self._artist_mbid_cache.keys()) - current_artist_keys
        for key in stale_album_keys:
            del self._album_mbid_cache[key]
        for key in stale_artist_keys:
            del self._artist_mbid_cache[key]

        # Phase 4: Enrich all entries from Lidarr library matching (skipped when Lidarr unavailable)
        resolved_albums = 0
        resolved_artists = 0

        if self._lidarr_album_index:
            for album in all_albums:
                if not album.name or album.name == "Unknown":
                    continue
                cache_key = f"{_normalize(album.name)}:{_normalize(album.artist)}"
                existing = self._album_mbid_cache.get(cache_key)
                if isinstance(existing, str):
                    # Overwrite with Lidarr data if available (corrects old MB-sourced or Navidrome-native MBIDs)
                    lidarr_match = self._lidarr_album_index.get(cache_key)
                    if not lidarr_match:
                        clean_key = f"{_normalize(_clean_album_name(album.name))}:{_normalize(album.artist)}"
                        if clean_key != cache_key:
                            lidarr_match = self._lidarr_album_index.get(clean_key)
                    if lidarr_match and lidarr_match[0] != existing:
                        self._album_mbid_cache[cache_key] = lidarr_match[0]
                        self._dirty = True
                        resolved_albums += 1
                    continue
                if isinstance(existing, tuple):
                    # Override negative entries when Lidarr now has a match
                    lidarr_hit = self._lidarr_album_index.get(cache_key)
                    if not lidarr_hit:
                        clean_key = f"{_normalize(_clean_album_name(album.name))}:{_normalize(album.artist)}"
                        if clean_key != cache_key:
                            lidarr_hit = self._lidarr_album_index.get(clean_key)
                    if lidarr_hit:
                        del self._album_mbid_cache[cache_key]
                    elif time.time() - existing[1] < _NEGATIVE_CACHE_TTL:
                        continue
                mbid = await self._resolve_album_mbid(album.name, album.artist)
                if mbid:
                    resolved_albums += 1

            for name in current_artist_names:
                norm = _normalize(name)
                existing = self._artist_mbid_cache.get(norm)
                if isinstance(existing, str):
                    lidarr_match = self._lidarr_artist_index.get(norm)
                    if lidarr_match and lidarr_match != existing:
                        self._artist_mbid_cache[norm] = lidarr_match
                        self._dirty = True
                        resolved_artists += 1
                    continue
                if isinstance(existing, tuple):
                    lidarr_hit = self._lidarr_artist_index.get(norm)
                    if lidarr_hit:
                        del self._artist_mbid_cache[norm]
                    elif time.time() - existing[1] < _NEGATIVE_CACHE_TTL:
                        continue
                mbid = await self._resolve_artist_mbid(name)
                if mbid:
                    resolved_artists += 1

        # Phase 5: Persist to SQLite
        if self._mbid_store and (self._dirty or stale_album_keys or stale_artist_keys):
            try:
                serializable_albums = {k: (v if isinstance(v, str) else None) for k, v in self._album_mbid_cache.items()}
                serializable_artists = {k: (v if isinstance(v, str) else None) for k, v in self._artist_mbid_cache.items()}
                await self._mbid_store.save_navidrome_album_mbid_index(serializable_albums)
                await self._mbid_store.save_navidrome_artist_mbid_index(serializable_artists)
                self._dirty = False
            except Exception:  # noqa: BLE001
                logger.warning("Failed to persist Navidrome MBID cache to disk", exc_info=True)

        # Phase 6: Rebuild the MBID -> navidrome_id reverse index from scratch.
        self._mbid_to_navidrome_id.clear()
        for album in all_albums:
            if not album.name or album.name == "Unknown":
                continue
            cache_key = f"{_normalize(album.name)}:{_normalize(album.artist)}"
            # Only use Lidarr-resolved MBIDs for reverse index
            mbid = _cache_get_mbid(self._album_mbid_cache, cache_key)
            if mbid:
                self._mbid_to_navidrome_id[mbid] = album.id

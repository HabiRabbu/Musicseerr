import asyncio
import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from core.exceptions import InvalidPlaylistDataError, PlaylistNotFoundError, SourceResolutionError
from infrastructure.cache.memory_cache import CacheInterface
from repositories.async_playlist_repository import AsyncPlaylistRepository
from repositories.playlist_repository import (
    PlaylistRecord,
    PlaylistRepository,
    PlaylistSummaryRecord,
    PlaylistTrackRecord,
)

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_COVER_SIZE = 2 * 1024 * 1024  # 2 MB
_MIME_TO_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_SAFE_ID_RE = re.compile(r"^[a-f0-9\-]+$")
VALID_SOURCE_TYPES = {"local", "jellyfin", "youtube", ""}
MAX_NAME_LENGTH = 100

_SOURCE_TYPE_ALIASES = {
    "local": "howler",
    "howler": "howler",
    "jellyfin": "jellyfin",
    "youtube": "youtube",
    "": "",
}


def _fuzzy_name_match(name1: str, name2: str) -> bool:
    if not name1 or not name2:
        return False
    n1, n2 = name1.lower().strip(), name2.lower().strip()
    if n1 == n2:
        return True
    if n1 in n2 or n2 in n1:
        return True
    return SequenceMatcher(None, n1, n2).ratio() > 0.6


class PlaylistService:
    def __init__(self, repo: PlaylistRepository, cache_dir: Path, cache: Optional[CacheInterface] = None):
        self._repo = AsyncPlaylistRepository(repo)
        self._cover_dir = cache_dir / "covers" / "playlists"
        self._cache = cache

    # -- Playlists --

    async def create_playlist(self, name: str) -> PlaylistRecord:
        stripped = name.strip() if name else ""
        if not stripped:
            raise InvalidPlaylistDataError("Playlist name must not be empty")
        if len(stripped) > MAX_NAME_LENGTH:
            raise InvalidPlaylistDataError(f"Playlist name must not exceed {MAX_NAME_LENGTH} characters")
        result = await self._repo.create_playlist(stripped)
        logger.info("Playlist created: id=%s name=%s", result.id, result.name)
        return result

    async def get_playlist(self, playlist_id: str) -> PlaylistRecord:
        result = await self._repo.get_playlist(playlist_id)
        if result is None:
            raise PlaylistNotFoundError(f"Playlist {playlist_id} not found")
        return result

    async def get_all_playlists(self) -> list[PlaylistSummaryRecord]:
        return await self._repo.get_all_playlists()

    async def get_playlist_with_tracks(
        self, playlist_id: str,
    ) -> tuple[PlaylistRecord, list[PlaylistTrackRecord]]:
        playlist = await self.get_playlist(playlist_id)
        tracks = await self._repo.get_tracks(playlist_id)
        return playlist, tracks

    async def update_playlist(
        self, playlist_id: str, name: Optional[str] = None,
    ) -> PlaylistRecord:
        if name is not None:
            stripped = name.strip()
            if not stripped:
                raise InvalidPlaylistDataError("Playlist name must not be empty")
            if len(stripped) > MAX_NAME_LENGTH:
                raise InvalidPlaylistDataError(f"Playlist name must not exceed {MAX_NAME_LENGTH} characters")
            name = stripped

        result = await self._repo.update_playlist(playlist_id, name=name)
        if result is None:
            raise PlaylistNotFoundError(f"Playlist {playlist_id} not found")
        logger.info("Playlist updated: id=%s", playlist_id)
        return result

    async def update_playlist_with_detail(
        self, playlist_id: str, name: Optional[str] = None,
    ) -> tuple[PlaylistRecord, list[PlaylistTrackRecord]]:
        playlist = await self.update_playlist(playlist_id, name=name)
        tracks = await self._repo.get_tracks(playlist_id)
        return playlist, tracks

    async def delete_playlist(self, playlist_id: str) -> None:
        deleted = await self._repo.delete_playlist(playlist_id)
        if not deleted:
            raise PlaylistNotFoundError(f"Playlist {playlist_id} not found")
        await asyncio.to_thread(self._delete_cover_file, playlist_id)
        logger.info("Playlist deleted: id=%s", playlist_id)

    # -- Tracks --

    async def add_tracks(
        self,
        playlist_id: str,
        tracks: list[dict],
        position: Optional[int] = None,
    ) -> list[PlaylistTrackRecord]:
        if not tracks:
            raise InvalidPlaylistDataError("Track list must not be empty")
        normalized_tracks: list[dict] = []
        for track in tracks:
            normalized = dict(track)
            st = normalized.get("source_type", "")
            if st and st not in _SOURCE_TYPE_ALIASES:
                raise InvalidPlaylistDataError(
                    f"Invalid source_type '{st}'. Allowed: {', '.join(sorted(_SOURCE_TYPE_ALIASES.keys() - {''}))}"  # noqa: E501
                )
            normalized["source_type"] = _SOURCE_TYPE_ALIASES.get(st, st)

            sources = normalized.get("available_sources")
            if sources is not None:
                normalized_sources: list[str] = []
                for source in sources:
                    if source not in _SOURCE_TYPE_ALIASES:
                        raise InvalidPlaylistDataError(
                            f"Invalid available source '{source}'. Allowed: {', '.join(sorted(_SOURCE_TYPE_ALIASES.keys() - {''}))}"  # noqa: E501
                        )
                    normalized_sources.append(_SOURCE_TYPE_ALIASES[source])
                normalized["available_sources"] = normalized_sources

            normalized_tracks.append(normalized)
        await self.get_playlist(playlist_id)
        result = await self._repo.add_tracks(playlist_id, normalized_tracks, position)
        logger.info("Added %d tracks to playlist %s", len(result), playlist_id)
        return result

    async def remove_track(self, playlist_id: str, track_id: str) -> None:
        removed = await self._repo.remove_track(playlist_id, track_id)
        if not removed:
            raise PlaylistNotFoundError(f"Track {track_id} not found in playlist {playlist_id}")
        logger.info("Removed track %s from playlist %s", track_id, playlist_id)

    async def reorder_track(
        self, playlist_id: str, track_id: str, new_position: int,
    ) -> int:
        if new_position < 0:
            raise InvalidPlaylistDataError("Position must be >= 0")
        result = await self._repo.reorder_track(playlist_id, track_id, new_position)
        if result is None:
            raise PlaylistNotFoundError(f"Track {track_id} not found in playlist {playlist_id}")
        logger.info("Reordered track %s to position %d in playlist %s", track_id, result, playlist_id)
        return result

    async def update_track_source(
        self,
        playlist_id: str,
        track_id: str,
        source_type: Optional[str] = None,
        available_sources: Optional[list[str]] = None,
        jf_service: object = None,
        local_service: object = None,
    ) -> PlaylistTrackRecord:
        if source_type is not None and source_type not in _SOURCE_TYPE_ALIASES:
            raise InvalidPlaylistDataError(
                f"Invalid source_type '{source_type}'. Allowed: {', '.join(sorted(_SOURCE_TYPE_ALIASES.keys() - {''}))}"  # noqa: E501
            )

        normalized_source = _SOURCE_TYPE_ALIASES.get(source_type, source_type)
        normalized_available_sources = available_sources
        if available_sources is not None:
            normalized_available_sources = []
            for source in available_sources:
                if source not in _SOURCE_TYPE_ALIASES:
                    raise InvalidPlaylistDataError(
                        f"Invalid available source '{source}'. Allowed: {', '.join(sorted(_SOURCE_TYPE_ALIASES.keys() - {''}))}"  # noqa: E501
                    )
                normalized_available_sources.append(_SOURCE_TYPE_ALIASES[source])

        new_track_source_id: Optional[str] = None
        if normalized_source:
            current_track = await self._repo.get_track(playlist_id, track_id)
            if current_track is None:
                raise PlaylistNotFoundError(f"Track {track_id} not found in playlist {playlist_id}")
            if normalized_source != current_track.source_type:
                new_track_source_id = await self._resolve_new_source_id(
                    current_track, normalized_source, jf_service, local_service,
                )

        result = await self._repo.update_track_source(
            playlist_id, track_id, normalized_source, normalized_available_sources,
            track_source_id=new_track_source_id,
        )
        if result is None:
            raise PlaylistNotFoundError(f"Track {track_id} not found in playlist {playlist_id}")
        logger.info("Updated track source: track=%s playlist=%s", track_id, playlist_id)
        return result

    async def get_tracks(self, playlist_id: str) -> list[PlaylistTrackRecord]:
        return await self._repo.get_tracks(playlist_id)

    async def check_track_membership(
        self, tracks: list[tuple[str, str, str]],
    ) -> dict[str, list[int]]:
        return await self._repo.check_track_membership(tracks)

    # -- Source resolution --

    async def resolve_track_sources(
        self,
        playlist_id: str,
        jf_service: object = None,
        local_service: object = None,
    ) -> dict[str, list[str]]:
        await self.get_playlist(playlist_id)
        tracks = await self._repo.get_tracks(playlist_id)
        if not tracks:
            return {}

        album_groups: dict[str, list[PlaylistTrackRecord]] = defaultdict(list)
        no_album_tracks: list[PlaylistTrackRecord] = []
        for t in tracks:
            if t.album_id and t.track_number is not None:
                album_groups[t.album_id].append(t)
            else:
                no_album_tracks.append(t)

        result: dict[str, list[str]] = {}
        for album_id, album_tracks in album_groups.items():
            jf_by_num, local_by_num = await self._resolve_album_sources(
                album_id, jf_service, local_service,
            )
            for t in album_tracks:
                sources = set()
                if t.source_type:
                    sources.add(t.source_type)

                jf_track = jf_by_num.get(t.track_number)
                if jf_track and _fuzzy_name_match(t.track_name, jf_track[0]):
                    sources.add("jellyfin")

                local_track = local_by_num.get(t.track_number)
                if local_track and _fuzzy_name_match(t.track_name, local_track[0]):
                    sources.add("howler")

                result[t.id] = sorted(sources)

        for t in no_album_tracks:
            result[t.id] = [t.source_type] if t.source_type else []

        return result

    async def _resolve_album_sources(
        self,
        album_id: str,
        jf_service: object,
        local_service: object,
    ) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]]]:
        cache_key = f"source_resolution:{album_id}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        jf_by_num: dict[int, tuple[str, str]] = {}
        local_by_num: dict[int, tuple[str, str]] = {}

        if jf_service is not None:
            try:
                match = await jf_service.match_album_by_mbid(album_id)
                if match.found:
                    for t in match.tracks:
                        jf_by_num[t.track_number] = (t.title, t.jellyfin_id)
            except Exception:
                logger.debug("Jellyfin source resolution failed for album %s", album_id, exc_info=True)

        if local_service is not None:
            try:
                match = await local_service.match_album_by_mbid(album_id)
                if match.found:
                    for t in match.tracks:
                        local_by_num[t.track_number] = (t.title, str(t.track_file_id))
            except Exception:
                logger.debug("Local source resolution failed for album %s", album_id, exc_info=True)

        resolved = (jf_by_num, local_by_num)
        if self._cache:
            await self._cache.set(cache_key, resolved, ttl_seconds=3600)
        return resolved

    async def _resolve_new_source_id(
        self,
        track: PlaylistTrackRecord,
        new_source_type: str,
        jf_service: object,
        local_service: object,
    ) -> str:
        if not track.album_id or track.track_number is None:
            raise SourceResolutionError(
                f"Cannot switch source for track '{track.track_name}': missing album_id or track_number"
            )

        jf_by_num, local_by_num = await self._resolve_album_sources(
            track.album_id, jf_service, local_service,
        )

        if new_source_type == "jellyfin":
            match_info = jf_by_num.get(track.track_number)
            if match_info and _fuzzy_name_match(track.track_name, match_info[0]):
                return match_info[1]
            raise SourceResolutionError(
                f"Track '{track.track_name}' not found in Jellyfin for album {track.album_id}"
            )

        if new_source_type == "howler":
            match_info = local_by_num.get(track.track_number)
            if match_info and _fuzzy_name_match(track.track_name, match_info[0]):
                return match_info[1]
            raise SourceResolutionError(
                f"Track '{track.track_name}' not found in local files for album {track.album_id}"
            )

        raise SourceResolutionError(f"Unsupported source type for resolution: {new_source_type}")

    # -- Cover art --

    async def upload_cover(
        self, playlist_id: str, data: bytes, content_type: str,
    ) -> str:
        await self.get_playlist(playlist_id)
        self._validate_cover_id(playlist_id)

        if content_type not in ALLOWED_IMAGE_TYPES:
            raise InvalidPlaylistDataError(
                f"Invalid image type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"
            )
        if len(data) > MAX_COVER_SIZE:
            raise InvalidPlaylistDataError("Image too large. Maximum size is 2 MB")  # defence-in-depth

        ext = _MIME_TO_EXT.get(content_type, ".jpg")
        file_path = self._cover_dir / f"{playlist_id}{ext}"

        def _write_cover() -> None:
            self._cover_dir.mkdir(parents=True, exist_ok=True)
            for old in self._cover_dir.glob(f"{playlist_id}.*"):
                try:
                    old.unlink()
                except OSError:
                    pass
            file_path.write_bytes(data)

        await asyncio.to_thread(_write_cover)

        cover_path = str(file_path)
        await self._repo.update_playlist(
            playlist_id, cover_image_path=cover_path,
        )

        cover_url = f"/api/v1/playlists/{playlist_id}/cover"
        return cover_url

    async def get_cover_path(self, playlist_id: str) -> Optional[Path]:
        playlist = await self.get_playlist(playlist_id)
        if not playlist.cover_image_path:
            return None
        path = Path(playlist.cover_image_path)
        exists = await asyncio.to_thread(path.exists)
        if exists:
            return path
        return None

    async def remove_cover(self, playlist_id: str) -> None:
        playlist = await self.get_playlist(playlist_id)
        if playlist.cover_image_path:
            cover_path = Path(playlist.cover_image_path)
            try:
                await asyncio.to_thread(cover_path.unlink, True)
            except OSError:
                pass
        await self._repo.update_playlist(
            playlist_id, cover_image_path=None,
        )

    # -- Helpers --

    @staticmethod
    def _validate_cover_id(playlist_id: str) -> None:
        if not _SAFE_ID_RE.match(playlist_id):
            raise InvalidPlaylistDataError("Invalid playlist ID for cover path")

    def _delete_cover_file(self, playlist_id: str) -> None:
        if not _SAFE_ID_RE.match(playlist_id):
            return
        for f in self._cover_dir.glob(f"{playlist_id}.*"):
            try:
                f.unlink()
            except OSError:
                pass

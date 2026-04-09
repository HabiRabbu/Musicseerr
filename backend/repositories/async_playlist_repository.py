import asyncio
from typing import Optional

from repositories.playlist_repository import (
    PlaylistRecord,
    PlaylistRepository,
    PlaylistSummaryRecord,
    PlaylistTrackRecord,
    _UNSET,
)


class AsyncPlaylistRepository:
    """Async wrapper around PlaylistRepository.

    Delegates all calls to asyncio.to_thread to avoid blocking the event loop.
    """

    def __init__(self, repo: PlaylistRepository):
        self._repo = repo

    async def create_playlist(self, name: str) -> PlaylistRecord:
        return await asyncio.to_thread(self._repo.create_playlist, name)

    async def get_playlist(self, playlist_id: str) -> Optional[PlaylistRecord]:
        return await asyncio.to_thread(self._repo.get_playlist, playlist_id)

    async def get_all_playlists(self) -> list[PlaylistSummaryRecord]:
        return await asyncio.to_thread(self._repo.get_all_playlists)

    async def update_playlist(
        self,
        playlist_id: str,
        name: Optional[str] = None,
        cover_image_path: Optional[str] = _UNSET,
    ) -> Optional[PlaylistRecord]:
        return await asyncio.to_thread(
            self._repo.update_playlist, playlist_id, name, cover_image_path,
        )

    async def delete_playlist(self, playlist_id: str) -> bool:
        return await asyncio.to_thread(self._repo.delete_playlist, playlist_id)

    async def add_tracks(
        self,
        playlist_id: str,
        tracks: list[dict],
        position: Optional[int] = None,
    ) -> list[PlaylistTrackRecord]:
        return await asyncio.to_thread(self._repo.add_tracks, playlist_id, tracks, position)

    async def remove_track(self, playlist_id: str, track_id: str) -> bool:
        return await asyncio.to_thread(self._repo.remove_track, playlist_id, track_id)

    async def remove_tracks(self, playlist_id: str, track_ids: list[str]) -> int:
        return await asyncio.to_thread(self._repo.remove_tracks, playlist_id, track_ids)

    async def reorder_track(
        self, playlist_id: str, track_id: str, new_position: int,
    ) -> Optional[int]:
        return await asyncio.to_thread(
            self._repo.reorder_track, playlist_id, track_id, new_position,
        )

    async def update_track_source(
        self,
        playlist_id: str,
        track_id: str,
        source_type: Optional[str] = None,
        available_sources: Optional[list[str]] = None,
        track_source_id: Optional[str] = None,
        plex_rating_key: Optional[str] = _UNSET,
    ) -> Optional[PlaylistTrackRecord]:
        return await asyncio.to_thread(
            self._repo.update_track_source, playlist_id, track_id,
            source_type, available_sources, track_source_id, plex_rating_key,
        )

    async def batch_update_available_sources(
        self,
        playlist_id: str,
        updates: dict[str, list[str]],
    ) -> int:
        return await asyncio.to_thread(
            self._repo.batch_update_available_sources, playlist_id, updates,
        )

    async def get_tracks(self, playlist_id: str) -> list[PlaylistTrackRecord]:
        return await asyncio.to_thread(self._repo.get_tracks, playlist_id)

    async def get_track(self, playlist_id: str, track_id: str) -> Optional[PlaylistTrackRecord]:
        return await asyncio.to_thread(self._repo.get_track, playlist_id, track_id)

    async def check_track_membership(
        self, tracks: list[tuple[str, str, str]],
    ) -> dict[str, list[int]]:
        return await asyncio.to_thread(self._repo.check_track_membership, tracks)

from typing import Any, Protocol

from models.library import LibraryAlbum
from models.request import QueueItem
from models.common import ServiceStatus


class LidarrRepositoryProtocol(Protocol):

    def is_configured(self) -> bool:
        ...

    async def get_library_albums(self) -> list[LibraryAlbum]:
        ...

    async def get_library_album_mbids(self) -> set[str]:
        ...

    async def get_library_artist_mbids(self) -> set[str]:
        ...

    async def add_album(self, album_mbid: str) -> dict[str, Any]:
        ...

    async def get_queue(self) -> list[QueueItem]:
        ...

    async def check_status(self) -> ServiceStatus:
        ...

    async def get_artist_details(self, artist_mbid: str) -> dict[str, Any] | None:
        ...

    async def get_album_details(self, album_mbid: str) -> dict[str, Any] | None:
        ...

    async def get_album_tracks(self, album_id: int) -> list[dict[str, Any]]:
        ...

    async def get_artist_albums(self, artist_mbid: str) -> list[dict[str, Any]]:
        ...

    async def get_artist_mbids(self) -> set[str]:
        ...

    async def get_library_mbids(self, include_release_ids: bool = True) -> set[str]:
        ...

    async def get_requested_mbids(self) -> set[str]:
        ...

    async def get_monitored_no_files_mbids(self) -> set[str]:
        ...

    async def delete_album(self, album_id: int, delete_files: bool = False) -> bool:
        ...

    async def delete_artist(self, artist_id: int, delete_files: bool = False) -> bool:
        ...

    async def get_queue_details(
        self, include_artist: bool = True, include_album: bool = True
    ) -> list[dict[str, Any]]:
        ...

    async def remove_queue_item(
        self, queue_id: int, remove_from_client: bool = True
    ) -> bool:
        ...

    async def trigger_album_search(self, album_ids: list[int]) -> dict[str, Any] | None:
        ...

    async def get_history_for_album(
        self,
        album_id: int,
        include_album: bool = True,
        include_artist: bool = True,
    ) -> list[dict[str, Any]]:
        ...

    async def get_track_file(self, track_file_id: int) -> dict[str, Any] | None:
        ...

    async def get_track_files_by_album(self, album_id: int) -> list[dict[str, Any]]:
        ...

    async def get_album_by_id(self, album_id: int) -> dict[str, Any] | None:
        ...

    async def get_album_by_mbid(self, mbid: str) -> dict[str, Any] | None:
        ...

    async def get_all_albums(self) -> list[dict[str, Any]]:
        ...

    async def get_recently_imported(self, limit: int = 20) -> list[LibraryAlbum]:
        ...

    async def update_artist_monitoring(
        self, artist_mbid: str, *, monitored: bool, monitor_new_items: str = "none",
    ) -> dict[str, Any]:
        ...

    async def set_monitored(self, album_mbid: str, monitored: bool) -> bool:
        ...

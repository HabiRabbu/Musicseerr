import logging
from datetime import datetime
from typing import Any
from models.library import LibraryAlbum
from infrastructure.cover_urls import prefer_release_group_cover_url
from .base import LidarrBase

logger = logging.getLogger(__name__)


class LidarrHistoryRepository(LidarrBase):
    async def get_recently_imported(self, limit: int = 20) -> list[LibraryAlbum]:
        try:
            album_dates: dict[str, tuple[int, dict]] = {}
            try:
                params = {
                    "page": 1,
                    "pageSize": limit * 10,
                    "sortKey": "date",
                    "sortDirection": "descending",
                    "includeAlbum": True,
                    "includeArtist": True,
                    "eventType": [2, 3, 8]
                }

                history_data = await self._get("/api/v1/history", params=params)

                if history_data and history_data.get("records"):
                    for record in history_data.get("records", []):
                        album_data = record.get("album", {})
                        if not album_data:
                            continue

                        album_mbid = album_data.get("foreignAlbumId")
                        if not album_mbid:
                            continue

                        date_added = None
                        if date_str := record.get("date"):
                            try:
                                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                date_added = int(dt.timestamp())
                            except Exception:  # noqa: BLE001
                                continue

                        if not date_added:
                            continue

                        if album_mbid not in album_dates or date_added > album_dates[album_mbid][0]:
                            album_dates[album_mbid] = (date_added, {
                                'album_data': album_data,
                                'artist_data': record.get("artist", {})
                            })
            except Exception:  # noqa: BLE001
                pass

            if len(album_dates) < limit * 2:
                album_dates = await self._supplement_with_album_dates(album_dates, limit)

            if not album_dates:
                return []

            sorted_albums = sorted(album_dates.items(), key=lambda x: x[1][0], reverse=True)
            recent_albums = sorted_albums[:limit]

            return self._build_library_albums(recent_albums)

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to get recently imported albums: {e}")
            return []

    async def _supplement_with_album_dates(self, album_dates: dict, limit: int) -> dict:
        try:
            albums_data = await self._get_all_albums_raw()

            albums_with_dates = []
            for album in albums_data:
                if not album.get("monitored", False):
                    continue

                album_id = album.get("id")
                album_mbid = album.get("foreignAlbumId")
                if not album_id or not album_mbid:
                    continue

                if album_mbid in album_dates:
                    continue

                stats = album.get("statistics", {})
                if stats.get("trackFileCount", 0) == 0:
                    continue

                date_added_str = album.get("dateAdded")
                if not date_added_str:
                    continue

                try:
                    date_added = datetime.fromisoformat(date_added_str.replace('Z', '+00:00'))
                    albums_with_dates.append((album, date_added, album_mbid))
                except Exception:  # noqa: BLE001
                    continue

            albums_with_dates.sort(key=lambda x: x[1], reverse=True)

            for album, most_recent, album_mbid in albums_with_dates[:limit * 2]:
                album_dates[album_mbid] = (int(most_recent.timestamp()), {
                    'album_data': album,
                    'artist_data': album.get("artist", {})
                })
        except Exception:  # noqa: BLE001
            pass

        return album_dates

    def _build_library_albums(self, recent_albums: list) -> list[LibraryAlbum]:
        out: list[LibraryAlbum] = []
        for album_mbid, (date_added, data) in recent_albums:
            album_data = data['album_data']
            artist_data = data['artist_data']

            artist = artist_data.get("artistName", "Unknown")
            artist_mbid = artist_data.get("foreignArtistId")

            year = None
            if date := album_data.get("releaseDate"):
                try:
                    year = int(date.split("-")[0])
                except ValueError:
                    pass

            album_id = album_data.get("id")
            cover_url = prefer_release_group_cover_url(
                album_mbid,
                self._get_album_cover_url(album_data.get("images", []), album_id),
                size=500,
            )

            out.append(
                LibraryAlbum(
                    artist=artist,
                    album=album_data.get("title"),
                    year=year,
                    monitored=album_data.get("monitored", False),
                    quality=None,
                    cover_url=cover_url,
                    musicbrainz_id=album_mbid,
                    artist_mbid=artist_mbid,
                    date_added=date_added,
                )
                )

            return out

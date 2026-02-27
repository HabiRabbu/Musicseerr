import asyncio
import logging
import time
from typing import Any, Optional
from core.exceptions import ExternalServiceError
from infrastructure.cover_urls import prefer_release_group_cover_url
from .base import LidarrBase
from .history import LidarrHistoryRepository

logger = logging.getLogger(__name__)


class LidarrAlbumRepository(LidarrHistoryRepository):
    async def get_all_albums(self) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/album")
        if not data or not isinstance(data, list):
            return []
        return data

    async def search_for_album(self, term: str) -> list[dict]:
        params = {"term": term}
        return await self._get("/api/v1/album/lookup", params=params)

    async def get_album_image_url(self, album_mbid: str, size: Optional[int] = 500) -> Optional[str]:
        cache_key = f"lidarr_album_image:{album_mbid}:{size or 'orig'}"
        cached_url = await self._cache.get(cache_key)
        if cached_url is not None:
            return cached_url if cached_url else None

        try:
            data = await self._get("/api/v1/album", params={"foreignAlbumId": album_mbid})
            if not data or not isinstance(data, list) or len(data) == 0:
                await self._cache.set(cache_key, "", ttl_seconds=300)
                return None

            album = data[0]
            album_id = album.get("id")
            images = album.get("images", [])

            if not album_id or not images:
                await self._cache.set(cache_key, "", ttl_seconds=300)
                return None

            cover_url = None
            for img in images:
                cover_type = img.get("coverType", "").lower()
                url_path = img.get("url", "")

                if not url_path:
                    continue

                if url_path.startswith("http"):
                    constructed_url = url_path
                else:
                    constructed_url = self._build_api_media_cover_url_album(album_id, url_path, size)

                if cover_type == "cover":
                    cover_url = constructed_url
                    break
                elif not cover_url:
                    cover_url = constructed_url

            if cover_url:
                logger.debug(f"[Lidarr:Album] Found cover for {album_mbid[:8]}: {cover_url[:60]}...")
                await self._cache.set(cache_key, cover_url, ttl_seconds=3600)
                return cover_url

            await self._cache.set(cache_key, "", ttl_seconds=300)
            return None

        except Exception as e:
            logger.debug(f"Failed to get album image from Lidarr for {album_mbid}: {e}")
            return None

    async def get_album_details(self, album_mbid: str) -> Optional[dict[str, Any]]:
        cache_key = f"lidarr_album_details:{album_mbid}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached if cached else None

        try:
            data = await self._get("/api/v1/album", params={"foreignAlbumId": album_mbid})
            if not data or not isinstance(data, list) or len(data) == 0:
                await self._cache.set(cache_key, "", ttl_seconds=300)
                return None

            album = data[0]
            album_id = album.get("id")

            cover_url = prefer_release_group_cover_url(
                album.get("foreignAlbumId"),
                self._get_album_cover_url(album.get("images", []), album_id),
                size=500,
            )

            links = []
            for link in album.get("links", []):
                link_name = link.get("name", "")
                link_url = link.get("url", "")
                if link_url:
                    links.append({"name": link_name, "url": link_url})

            artist_data = album.get("artist", {})

            releases = album.get("releases", [])
            primary_release = None
            for rel in releases:
                if rel.get("monitored"):
                    primary_release = rel
                    break
            if not primary_release and releases:
                primary_release = releases[0]

            media = []
            track_count = 0
            if primary_release:
                for medium in primary_release.get("media", []):
                    medium_info = {
                        "number": medium.get("mediumNumber", 1),
                        "format": medium.get("mediumFormat", "Unknown"),
                        "track_count": medium.get("mediumTrackCount", 0),
                    }
                    media.append(medium_info)
                    track_count += medium.get("mediumTrackCount", 0)

            result = {
                "id": album_id,
                "title": album.get("title", "Unknown"),
                "mbid": album.get("foreignAlbumId"),
                "overview": album.get("overview"),
                "disambiguation": album.get("disambiguation"),
                "album_type": album.get("albumType"),
                "secondary_types": album.get("secondaryTypes", []),
                "release_date": album.get("releaseDate"),
                "genres": album.get("genres", []),
                "links": links,
                "cover_url": cover_url,
                "monitored": album.get("monitored", False),
                "statistics": album.get("statistics", {}),
                "ratings": album.get("ratings", {}),
                "artist_name": artist_data.get("artistName", "Unknown"),
                "artist_mbid": artist_data.get("foreignArtistId"),
                "media": media,
                "track_count": track_count,
            }

            await self._cache.set(cache_key, result, ttl_seconds=300)
            logger.debug(f"[Lidarr] Fetched album details for {album_mbid[:8]}")
            return result

        except Exception as e:
            logger.debug(f"Failed to get album details from Lidarr for {album_mbid}: {e}")
            return None

    async def get_album_tracks(self, album_id: int) -> list[dict[str, Any]]:
        cache_key = f"lidarr_album_tracks:{album_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = await self._get("/api/v1/track", params={"albumId": album_id})
            if not data or not isinstance(data, list):
                await self._cache.set(cache_key, [], ttl_seconds=300)
                return []

            tracks = []
            for track in data:
                track_info = {
                    "position": track.get("absoluteTrackNumber", 0),
                    "disc_number": track.get("mediumNumber", 1),
                    "title": track.get("title", "Unknown"),
                    "duration_ms": track.get("duration", 0),
                    "track_file_id": track.get("trackFileId"),
                    "has_file": track.get("hasFile", False),
                }
                tracks.append(track_info)

            tracks.sort(key=lambda t: (t["disc_number"], t["position"]))

            await self._cache.set(cache_key, tracks, ttl_seconds=300)
            logger.debug(f"[Lidarr] Fetched {len(tracks)} tracks for album ID {album_id}")
            return tracks

        except Exception as e:
            logger.debug(f"Failed to get tracks from Lidarr for album ID {album_id}: {e}")
            return []

    async def get_track_file(self, track_file_id: int) -> dict[str, Any] | None:
        cache_key = f"lidarr_trackfile:{track_file_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = await self._get(f"/api/v1/trackfile/{track_file_id}")
            if data:
                await self._cache.set(cache_key, data, ttl_seconds=600)
            return data
        except Exception as e:
            logger.error("Failed to get track file %s: %s", track_file_id, e)
            return None

    async def get_track_files_by_album(self, album_id: int) -> list[dict[str, Any]]:
        cache_key = f"lidarr_album_trackfiles_raw:{album_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = await self._get(
                "/api/v1/trackfile",
                params={"albumId": album_id},
            )
            if not data or not isinstance(data, list):
                return []
            await self._cache.set(cache_key, data, ttl_seconds=300)
            return data
        except Exception as e:
            logger.error("Failed to get track files for album %s: %s", album_id, e)
            return []

    async def _get_album_by_foreign_id(self, album_mbid: str) -> Optional[dict[str, Any]]:
        try:
            items = await self._get("/api/v1/album", params={"foreignAlbumId": album_mbid})
            return items[0] if items else None
        except Exception as e:
            logger.warning(f"Error getting album by foreign ID {album_mbid}: {e}")
            return None

    async def delete_album(self, album_id: int, delete_files: bool = False) -> bool:
        try:
            params = {"deleteFiles": str(delete_files).lower(), "addImportListExclusion": "false"}
            await self._delete(f"/api/v1/album/{album_id}", params=params)
            logger.info(f"Deleted album ID {album_id} (deleteFiles={delete_files})")
            return True
        except Exception as e:
            logger.error(f"Failed to delete album {album_id}: {e}")
            raise

    async def add_album(self, musicbrainz_id: str, artist_repo) -> dict:
        if not musicbrainz_id or not isinstance(musicbrainz_id, str):
            raise ExternalServiceError("Invalid MBID provided")

        lookup = await self._get("/api/v1/album/lookup", params={"term": f"mbid:{musicbrainz_id}"})
        if not lookup:
            raise ExternalServiceError(
                f"Album not found in Lidarr lookup (MBID: {musicbrainz_id})"
            )

        candidate = next(
            (a for a in lookup if a.get("foreignAlbumId") == musicbrainz_id),
            lookup[0]
        )
        album_title = candidate.get("title", "Unknown Album")
        album_type = candidate.get("albumType", "Unknown")
        secondary_types = candidate.get("secondaryTypes", [])

        artist_info = candidate.get("artist") or {}
        artist_mbid = artist_info.get("mbId") or artist_info.get("foreignArtistId")
        artist_name = artist_info.get("artistName")
        if not artist_mbid:
            raise ExternalServiceError("Album lookup did not include artist MBID")

        artist = await artist_repo._ensure_artist_exists(artist_mbid, artist_name)
        artist_id = artist["id"]

        album_obj = await self._get_album_by_foreign_id(musicbrainz_id)
        action = "exists"

        if not album_obj:
            async def album_is_indexed():
                a = await self._get_album_by_foreign_id(musicbrainz_id)
                return a and a.get("id") and a.get("releases")

            album_obj = await self._wait_for(album_is_indexed, timeout=60.0, poll=3.0)

            if not album_obj:
                profile_id = artist.get("qualityProfileId")
                if profile_id is None:
                    try:
                        qps = await self._get("/api/v1/qualityprofile")
                        if not qps:
                            raise ExternalServiceError("No quality profiles in Lidarr")
                        profile_id = qps[0]["id"]
                    except Exception:
                        profile_id = self._settings.quality_profile_id

                payload = {
                    "title": album_title,
                    "artistId": artist_id,
                    "foreignAlbumId": musicbrainz_id,
                    "monitored": True,
                    "anyReleaseOk": True,
                    "profileId": profile_id,
                    "addOptions": {"addType": "automatic", "searchForNewAlbum": True},
                }

                try:
                    album_obj = await self._post("/api/v1/album", payload)
                    action = "added"
                    album_obj = await self._wait_for(album_is_indexed, timeout=120.0, poll=2.0)
                except Exception as e:
                    if "POST failed" in str(e) or "405" in str(e):
                        raise ExternalServiceError(
                            f"Cannot add this {album_type}. "
                            f"Lidarr rejected adding '{album_title}'. This is likely because your Lidarr "
                            f"Metadata Profile is configured to exclude {album_type}s{' (' + ', '.join(secondary_types) + ')' if secondary_types else ''}. "
                            f"To fix this: Go to Lidarr -> Settings -> Profiles -> Metadata Profiles, "
                            f"and enable '{album_type}' in your active profile."
                        )
                    else:
                        raise

        if not album_obj or "id" not in album_obj:
            raise ExternalServiceError(
                f"Cannot add this {album_type}. "
                f"'{album_title}' could not be found in Lidarr after the artist refresh. This usually means "
                f"your Lidarr Metadata Profile is configured to exclude {album_type}s. "
                f"To fix this: Go to Lidarr -> Settings -> Profiles -> Metadata Profiles, "
                f"enable '{album_type}', then refresh the artist in Lidarr."
            )

        album_id = album_obj["id"]

        await self._wait_for_artist_commands_to_complete(artist_id, timeout=600.0)
        await self._monitor_artist_and_album(artist_id, album_id, musicbrainz_id, album_title)

        try:
            await self._post_command({"name": "AlbumSearch", "albumIds": [album_id]})
        except Exception:
            pass

        final_album = await self._get_album_by_foreign_id(musicbrainz_id)

        if final_album and not final_album.get("monitored"):
            try:
                await self._put("/api/v1/album/monitor", {
                    "albumIds": [album_id],
                    "monitored": True
                })
                await asyncio.sleep(2.0)
                final_album = await self._get_album_by_foreign_id(musicbrainz_id)
            except Exception:
                pass

        await self._cache.clear_prefix("lidarr:library:mbids:")
        await self._cache.clear_prefix("lidarr:artists:mbids")
        await self._cache.clear_prefix("lidarr_requested")

        msg = "Album added & monitored" if action == "added" else "Album exists; monitored ensured"
        return {
            "message": f"{msg}: {album_title}",
            "payload": final_album or album_obj
        }

    async def _wait_for_artist_commands_to_complete(self, artist_id: int, timeout: float = 600.0) -> None:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                commands = await self._get("/api/v1/command")
                if not commands:
                    break

                has_running_commands = False
                for cmd in commands:
                    status = cmd.get("status") or cmd.get("state")
                    if str(status).lower() in ["queued", "started"]:
                        body = cmd.get("body", {})
                        cmd_artist_id = body.get("artistId")
                        cmd_artist_ids = body.get("artistIds", [])

                        if cmd_artist_id == artist_id or artist_id in cmd_artist_ids:
                            has_running_commands = True
                            break

                if not has_running_commands:
                    break

            except Exception as e:
                logger.warning(f"Error checking command status: {e}")

            await asyncio.sleep(5.0)

        await asyncio.sleep(5.0)

    async def _monitor_artist_and_album(
        self,
        artist_id: int,
        album_id: int,
        album_mbid: str,
        album_title: str,
        max_attempts: int = 3
    ) -> None:
        for attempt in range(max_attempts):
            try:
                await self._put(
                    "/api/v1/artist/editor",
                    {"artistIds": [artist_id], "monitored": True, "monitorNewItems": "none"},
                )

                await asyncio.sleep(5.0 + (attempt * 3.0))

                await self._put("/api/v1/album/monitor", {"albumIds": [album_id], "monitored": True})

                async def both_monitored():
                    album = await self._get_album_by_foreign_id(album_mbid)
                    artist_data = await self._get(f"/api/v1/artist/{artist_id}")
                    return (album and album.get("monitored")) and (artist_data and artist_data.get("monitored"))

                timeout = 20.0 + (attempt * 10.0)
                if await self._wait_for(both_monitored, timeout=timeout, poll=1.0):
                    return

                if attempt < max_attempts - 1:
                    logger.warning(f"Monitoring verification failed, attempt {attempt + 1}/{max_attempts}")
                    await asyncio.sleep(5.0)

            except Exception as e:
                if attempt == max_attempts - 1:
                    raise ExternalServiceError(
                        f"Failed to set monitoring status after {max_attempts} attempts: {str(e)}"
                    )
                await asyncio.sleep(5.0)

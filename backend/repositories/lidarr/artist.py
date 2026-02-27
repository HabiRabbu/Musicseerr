import asyncio
import logging
from typing import Any, Optional
from core.exceptions import ExternalServiceError
from infrastructure.cover_urls import prefer_release_group_cover_url
from .base import LidarrBase

logger = logging.getLogger(__name__)


class LidarrArtistRepository(LidarrBase):
    async def get_artist_image_url(self, artist_mbid: str, size: Optional[int] = 250) -> Optional[str]:
        cache_key = f"lidarr_artist_image:{artist_mbid}:{size or 'orig'}"
        cached_url = await self._cache.get(cache_key)
        if cached_url is not None:
            if cached_url:
                logger.debug(f"[Lidarr:Image] Cache HIT for {artist_mbid[:8]}")
            else:
                logger.debug(f"[Lidarr:Image] Cache HIT (negative) for {artist_mbid[:8]}")
            return cached_url if cached_url else None

        logger.info(f"[Lidarr:Image] Cache MISS - querying Lidarr for {artist_mbid[:8]}")
        try:
            data = await self._get("/api/v1/artist", params={"mbId": artist_mbid})
            if not data or not isinstance(data, list) or len(data) == 0:
                logger.info(f"[Lidarr:Image] Artist not found in Lidarr for {artist_mbid[:8]}")
                await self._cache.set(cache_key, "", ttl_seconds=300)
                return None

            artist = data[0]
            artist_id = artist.get("id")
            artist_name = artist.get("artistName", "Unknown")
            images = artist.get("images", [])
            logger.debug(f"[Lidarr:Image] Found artist '{artist_name}' (id={artist_id}) with {len(images)} images")

            if not artist_id or not images:
                logger.info(f"[Lidarr:Image] No images for {artist_mbid[:8]} ({artist_name})")
                await self._cache.set(cache_key, "", ttl_seconds=300)
                return None

            poster_url = None
            fanart_url = None
            for img in images:
                cover_type = img.get("coverType", "").lower()
                url_path = img.get("url", "")

                if not url_path:
                    continue

                if url_path.startswith("http"):
                    constructed_url = url_path
                else:
                    constructed_url = self._build_api_media_cover_url(artist_id, url_path, size)

                if cover_type == "poster":
                    poster_url = constructed_url
                    break
                elif cover_type == "fanart" and not fanart_url:
                    fanart_url = constructed_url

            image_url = poster_url or fanart_url
            if image_url:
                logger.info(f"[Lidarr:Image] Found image for {artist_mbid[:8]} ({artist_name}): {image_url[:60]}...")
                await self._cache.set(cache_key, image_url, ttl_seconds=3600)
                return image_url

            logger.info(f"[Lidarr:Image] No poster/fanart for {artist_mbid[:8]} ({artist_name})")
            await self._cache.set(cache_key, "", ttl_seconds=300)
            return None

        except Exception as e:
            logger.warning(f"[Lidarr:Image] Exception for {artist_mbid[:8]}: {e}")
            return None

    async def get_artist_details(self, artist_mbid: str) -> Optional[dict[str, Any]]:
        cache_key = f"lidarr_artist_details:{artist_mbid}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached if cached else None

        try:
            data = await self._get("/api/v1/artist", params={"mbId": artist_mbid})
            if not data or not isinstance(data, list) or len(data) == 0:
                await self._cache.set(cache_key, "", ttl_seconds=300)
                return None

            artist = data[0]
            artist_id = artist.get("id")

            image_urls = self._get_artist_image_urls(artist.get("images", []), artist_id)

            links = []
            for link in artist.get("links", []):
                link_name = link.get("name", "")
                link_url = link.get("url", "")
                if link_url:
                    links.append({"name": link_name, "url": link_url})

            result = {
                "id": artist_id,
                "name": artist.get("artistName", "Unknown"),
                "mbid": artist.get("foreignArtistId"),
                "overview": artist.get("overview"),
                "disambiguation": artist.get("disambiguation"),
                "artist_type": artist.get("artistType"),
                "status": artist.get("status"),
                "genres": artist.get("genres", []),
                "links": links,
                "poster_url": image_urls["poster"],
                "fanart_url": image_urls["fanart"],
                "banner_url": image_urls["banner"],
                "monitored": artist.get("monitored", False),
                "statistics": artist.get("statistics", {}),
                "ratings": artist.get("ratings", {}),
            }

            await self._cache.set(cache_key, result, ttl_seconds=300)
            logger.debug(f"[Lidarr] Fetched artist details for {artist_mbid[:8]}")
            return result

        except Exception as e:
            logger.debug(f"Failed to get artist details from Lidarr for {artist_mbid}: {e}")
            return None

    async def get_artist_albums(self, artist_mbid: str) -> list[dict[str, Any]]:
        cache_key = f"lidarr_artist_albums:{artist_mbid}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            artist_data = await self._get("/api/v1/artist", params={"mbId": artist_mbid})
            if not artist_data or not isinstance(artist_data, list) or len(artist_data) == 0:
                await self._cache.set(cache_key, [], ttl_seconds=300)
                return []

            artist_id = artist_data[0].get("id")
            if not artist_id:
                await self._cache.set(cache_key, [], ttl_seconds=300)
                return []

            album_data = await self._get("/api/v1/album", params={"artistId": artist_id, "includeAllArtistAlbums": True})
            if not album_data or not isinstance(album_data, list):
                await self._cache.set(cache_key, [], ttl_seconds=300)
                return []

            albums = []
            for album in album_data:
                album_id = album.get("id")
                album_mbid = album.get("foreignAlbumId")
                images = album.get("images", [])
                cover_url = None
                for img in images:
                    url_path = img.get("url", "")
                    if url_path:
                        if url_path.startswith("http"):
                            cover_url = url_path
                        else:
                            cover_url = self._build_api_media_cover_url_album(album_id, url_path, 250)
                        break

                cover_url = prefer_release_group_cover_url(album_mbid, cover_url, size=500)

                year = None
                if release_date := album.get("releaseDate"):
                    try:
                        year = int(release_date.split("-")[0])
                    except (ValueError, IndexError):
                        pass

                statistics = album.get("statistics", {})
                track_file_count = statistics.get("trackFileCount", 0)

                album_info = {
                    "id": album_id,
                    "title": album.get("title", "Unknown"),
                    "mbid": album_mbid,
                    "album_type": album.get("albumType"),
                    "secondary_types": album.get("secondaryTypes", []),
                    "release_date": album.get("releaseDate"),
                    "year": year,
                    "monitored": album.get("monitored", False),
                    "track_file_count": track_file_count,
                    "cover_url": cover_url,
                    "genres": album.get("genres", []),
                }
                albums.append(album_info)

            albums.sort(key=lambda a: a.get("release_date") or "", reverse=True)

            await self._cache.set(cache_key, albums, ttl_seconds=300)
            logger.debug(f"[Lidarr] Fetched {len(albums)} albums for artist {artist_mbid[:8]}")
            return albums

        except Exception as e:
            logger.debug(f"Failed to get artist albums from Lidarr for {artist_mbid}: {e}")
            return []

    async def _get_artist_by_id(self, artist_id: int) -> Optional[dict[str, Any]]:
        try:
            return await self._get(f"/api/v1/artist/{artist_id}")
        except Exception as e:
            logger.warning(f"Error getting artist {artist_id}: {e}")
            return None

    async def delete_artist(self, artist_id: int, delete_files: bool = False) -> bool:
        try:
            params = {"deleteFiles": str(delete_files).lower(), "addImportListExclusion": "false"}
            await self._delete(f"/api/v1/artist/{artist_id}", params=params)
            logger.info(f"Deleted artist ID {artist_id} (deleteFiles={delete_files})")
            return True
        except Exception as e:
            logger.error(f"Failed to delete artist {artist_id}: {e}")
            raise

    async def _ensure_artist_exists(self, artist_mbid: str, artist_name_hint: Optional[str] = None) -> dict[str, Any]:
        try:
            items = await self._get("/api/v1/artist", params={"mbId": artist_mbid})
            if items:
                logger.info(f"Artist already exists: {items[0].get('artistName')}")
                return items[0]
        except Exception:
            pass

        try:
            roots = await self._get("/api/v1/rootfolder")
            if not roots:
                raise ExternalServiceError("No root folders configured in Lidarr")
            root = next((r for r in roots if r.get("accessible", True)), roots[0])
        except Exception as e:
            raise ExternalServiceError(f"Failed to get root folders: {e}")

        qp_id = root.get("defaultQualityProfileId") or self._settings.quality_profile_id
        mp_id = root.get("defaultMetadataProfileId") or self._settings.metadata_profile_id

        try:
            lookup = await self._get("/api/v1/artist/lookup", params={"term": f"mbid:{artist_mbid}"})
            if not lookup:
                raise ExternalServiceError(f"Artist not found in lookup: {artist_mbid}")
            remote = lookup[0]
            artist_name = remote.get("artistName") or artist_name_hint or "Unknown Artist"
        except Exception as e:
            raise ExternalServiceError(f"Failed to lookup artist: {e}")

        payload = {
            "artistName": artist_name,
            "mbId": artist_mbid,
            "foreignArtistId": artist_mbid,
            "qualityProfileId": qp_id,
            "metadataProfileId": mp_id,
            "rootFolderPath": root.get("path"),
            "monitored": False,
            "monitorNewItems": "none",
            "addOptions": {
                "monitor": "none",
                "monitored": False,
                "searchForMissingAlbums": False,
            },
        }

        try:
            created = await self._post("/api/v1/artist", payload)
            artist_id = created["id"]
            logger.info(f"Created artist {artist_name} (ID: {artist_id}), triggering refresh commands")

            logger.info(f"Refreshing artist {artist_name} library (this may take several minutes)...")
            await self._await_command(
                {"name": "RefreshArtist", "artistId": artist_id},
                timeout=600.0
            )

            logger.info(f"Rescanning artist {artist_name} library...")
            await self._await_command(
                {"name": "RescanArtist", "artistId": artist_id},
                timeout=300.0
            )

            await asyncio.sleep(5.0)

            logger.info(f"Artist {artist_name} library refresh complete")
            return created
        except Exception as e:
            raise ExternalServiceError(f"Failed to add artist: {e}")

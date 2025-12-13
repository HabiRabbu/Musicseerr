import asyncio
import httpx
import logging
import time
from typing import Any, Optional
from datetime import datetime
from core.config import Settings
from core.exceptions import ExternalServiceError
from api.v1.schemas.library import LibraryAlbum
from api.v1.schemas.request import QueueItem
from api.v1.schemas.common import ServiceStatus
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import (
    lidarr_library_mbids_key,
    lidarr_artist_mbids_key,
)
from infrastructure.resilience.retry import with_retry, CircuitBreaker

logger = logging.getLogger(__name__)

_lidarr_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="lidarr"
)


class LidarrRepository:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        cache: CacheInterface
    ):
        self._settings = settings
        self._client = http_client
        self._cache = cache
        self._base_url = settings.lidarr_url
    
    def _get_headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._settings.lidarr_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    
    @with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        circuit_breaker=_lidarr_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError, ExternalServiceError)
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{self._base_url}{endpoint}"
        
        try:
            response = await self._client.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
            )
            
            if method == "GET" and response.status_code != 200:
                raise ExternalServiceError(
                    f"Lidarr {method} failed ({response.status_code})",
                    response.text
                )
            elif method in ("POST", "PUT") and response.status_code not in (200, 201, 202):
                raise ExternalServiceError(
                    f"Lidarr {method} failed ({response.status_code})",
                    response.text
                )
            
            try:
                return response.json()
            except ValueError:
                return None
        
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"Lidarr request failed: {str(e)}")
    
    async def _get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> Any:
        return await self._request("GET", endpoint, params=params)
    
    async def _post(self, endpoint: str, data: dict[str, Any]) -> Any:
        return await self._request("POST", endpoint, json_data=data)
    
    async def _put(self, endpoint: str, data: dict[str, Any]) -> Any:
        return await self._request("PUT", endpoint, json_data=data)
    
    async def get_status(self) -> ServiceStatus:
        try:
            data = await self._get("/api/v1/system/status")
            return ServiceStatus(status="ok", version=data.get("version"))
        except Exception as e:
            return ServiceStatus(status="error", message=str(e))
    
    async def get_library(self, include_unmonitored: bool = False) -> list[LibraryAlbum]:
        data = await self._get("/api/v1/album")
        out: list[LibraryAlbum] = []
        filtered_count = 0
        
        for item in data:
            is_monitored = item.get("monitored", False)
            
            if not is_monitored and not include_unmonitored:
                filtered_count += 1
                continue
        
            artist_data = item.get("artist", {})
            artist = artist_data.get("artistName", "Unknown")
            artist_mbid = artist_data.get("foreignArtistId")
            
            year = None
            if date := item.get("releaseDate"):
                try:
                    year = int(date.split("-")[0])
                except ValueError:
                    pass
            
            cover = None
            if imgs := item.get("images"):
                first = imgs[0] if imgs else {}
                cover = first.get("remoteUrl") or first.get("url")
            
            date_added = None
            if added_str := item.get("added"):
                try:
                    dt = datetime.fromisoformat(added_str.replace('Z', '+00:00'))
                    date_added = int(dt.timestamp())
                except Exception as e:
                    logger.warning(f"Failed to parse date_added '{added_str}' for album '{item.get('title')}': {e}")
            
            out.append(
                LibraryAlbum(
                    artist=artist,
                    album=item.get("title"),
                    year=year,
                    monitored=item.get("monitored", False),
                    quality=None,
                    cover_url=cover,
                    musicbrainz_id=item.get("foreignAlbumId"),
                    artist_mbid=artist_mbid,
                    date_added=date_added,
                )
            )
        
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} unmonitored albums from library")
        
        return out
    
    async def get_artists_from_library(self, include_unmonitored: bool = False) -> list[dict]:
        albums_data = await self._get("/api/v1/album")
        artists_dict: dict[str, dict] = {}
        filtered_count = 0
        
        for item in albums_data:
            is_monitored = item.get("monitored", False)
            
            if not is_monitored and not include_unmonitored:
                filtered_count += 1
                continue
            
            artist_data = item.get("artist", {})
            artist_mbid = artist_data.get("foreignArtistId")
            artist_name = artist_data.get("artistName", "Unknown")
            
            if not artist_mbid:
                continue
            
            date_added = None
            if added_str := item.get("added"):
                try:
                    dt = datetime.fromisoformat(added_str.replace('Z', '+00:00'))
                    date_added = int(dt.timestamp())
                except Exception as e:
                    logger.warning(f"Failed to parse date_added '{added_str}' for artist '{artist_name}': {e}")
            
            if artist_mbid not in artists_dict:
                artists_dict[artist_mbid] = {
                    'mbid': artist_mbid,
                    'name': artist_name,
                    'album_count': 0,
                    'date_added': date_added
                }
            
            artists_dict[artist_mbid]['album_count'] += 1
            if date_added and (not artists_dict[artist_mbid]['date_added'] or 
                              date_added < artists_dict[artist_mbid]['date_added']):
                artists_dict[artist_mbid]['date_added'] = date_added
        
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} unmonitored albums from artist extraction")
        
        return list(artists_dict.values())
    
    async def get_library_grouped(self) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/album")
        grouped: dict[str, list[dict[str, Any]]] = {}

        for item in data:
            artist = item.get("artist", {}).get("artistName", "Unknown")
            title = item.get("title")
            year = None
            if date := item.get("releaseDate"):
                try:
                    year = int(date.split("-")[0])
                except ValueError:
                    pass

            cover = None
            if imgs := item.get("images"):
                first = imgs[0] if imgs else {}
                cover = first.get("remoteUrl") or first.get("url")

            grouped.setdefault(artist, []).append(
                {
                    "title": title,
                    "year": year,
                    "monitored": item.get("monitored", False),
                    "cover_url": cover,
                }
            )

        return [{"artist": artist, "albums": albums} for artist, albums in grouped.items()]
    
    async def get_library_mbids(self, include_release_ids: bool = True) -> set[str]:
        cache_key = lidarr_library_mbids_key(include_release_ids)
        
        cached_result = await self._cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        data = await self._get("/api/v1/album")
        ids: set[str] = set()
        for item in data:
            if not item.get("monitored", False):
                continue
                
            rg = item.get("foreignAlbumId")
            if isinstance(rg, str):
                ids.add(rg.lower())
            if include_release_ids:
                for rel in item.get("releases", []) or []:
                    rid = rel.get("foreignId")
                    if isinstance(rid, str):
                        ids.add(rid.lower())
        
        await self._cache.set(cache_key, ids, ttl_seconds=300)
        return ids
    
    async def get_artist_mbids(self) -> set[str]:
        cache_key = lidarr_artist_mbids_key()
        
        cached_result = await self._cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        data = await self._get("/api/v1/artist")
        ids: set[str] = set()
        for item in data:
            if not item.get("monitored", False):
                continue
            mbid = item.get("foreignArtistId") or item.get("mbId")
            if isinstance(mbid, str):
                ids.add(mbid.lower())
        
        await self._cache.set(cache_key, ids, ttl_seconds=300)
        return ids
    
    async def get_queue(self) -> list[QueueItem]:
        data = await self._get("/api/v1/queue")
        items = data.get("records", []) if isinstance(data, dict) else data
        
        queue_items = []
        for item in items:
            album_data = item.get("album", {})
            artist_data = album_data.get("artist", {})
            
            queue_items.append(
                QueueItem(
                    artist=artist_data.get("artistName", "Unknown"),
                    album=album_data.get("title", "Unknown"),
                    status=item.get("status", "unknown"),
                    progress=None,
                    eta=None,
                    musicbrainz_id=album_data.get("foreignAlbumId"),
                )
            )
        
        return queue_items
    
    async def add_album(self, musicbrainz_id: str) -> dict:
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
        
        artist = await self._ensure_artist_exists(artist_mbid, artist_name)
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
        
        await self._cache.clear_prefix("library_mbids:")
        await self._cache.clear_prefix("artist_mbids")
        
        msg = "Album added & monitored" if action == "added" else "Album exists; monitored ensured"
        return {
            "message": f"{msg}: {album_title}",
            "payload": final_album or album_obj
        }
    
    async def _get_album_by_foreign_id(self, album_mbid: str) -> Optional[dict[str, Any]]:
        try:
            items = await self._get("/api/v1/album", params={"foreignAlbumId": album_mbid})
            return items[0] if items else None
        except Exception as e:
            logger.warning(f"Error getting album by foreign ID {album_mbid}: {e}")
            return None
    
    async def _get_artist_by_id(self, artist_id: int) -> Optional[dict[str, Any]]:
        try:
            return await self._get(f"/api/v1/artist/{artist_id}")
        except Exception as e:
            logger.warning(f"Error getting artist {artist_id}: {e}")
            return None
    
    async def _post_command(self, body: dict[str, Any]) -> Any:
        try:
            return await self._post("/api/v1/command", body)
        except Exception:
            return None

    async def _get_command(self, cmd_id: int) -> Any:
        return await self._get(f"/api/v1/command/{cmd_id}")

    async def _await_command(self, body: dict[str, Any], timeout: float = 60.0, poll: float = 0.5) -> dict[str, Any] | None:
        try:
            cmd = await self._post_command(body)
            if not cmd or "id" not in cmd:
                await asyncio.sleep(min(timeout, 5.0))
                return None
            
            cmd_id = cmd["id"]
            deadline = time.monotonic() + timeout
            last_status = None
            
            while time.monotonic() < deadline:
                await asyncio.sleep(poll)
                try:
                    status = await self._get_command(cmd_id)
                    last_status = status
                except Exception:
                    continue
                
                state = (status or {}).get("status") or (status or {}).get("state")
                if str(state).lower() in {"completed", "failed", "aborted", "cancelled"}:
                    return status
            
            return last_status
        except Exception:
            return None

    async def _wait_for(
        self,
        fetch_coro_factory,
        stop=lambda v: bool(v),
        timeout: float = 30.0,
        poll: float = 0.5
    ):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                last = await fetch_coro_factory()
                if stop(last):
                    return last
            except Exception:
                pass
            await asyncio.sleep(poll)
        return last

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
    
    async def search_for_album(self, term: str) -> list[dict]:
        params = {"term": term}
        return await self._get("/api/v1/album/lookup", params=params)
    
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
                            except Exception:
                                continue
                        
                        if not date_added:
                            continue
                        
                        if album_mbid not in album_dates or date_added > album_dates[album_mbid][0]:
                            album_dates[album_mbid] = (date_added, {
                                'album_data': album_data,
                                'artist_data': record.get("artist", {})
                            })
                    
                    logger.info(f"Found {len(album_dates)} unique albums from {len(history_data.get('records', []))} history records")
            except Exception as e:
                logger.warning(f"Failed to get history data: {e}")
            
            if len(album_dates) < limit * 2:
                try:
                    albums_data, all_track_files = await asyncio.gather(
                        self._get("/api/v1/album"),
                        self._get("/api/v1/trackfile")
                    )
                    
                    trackfile_dates_by_album: dict[int, datetime] = {}
                    for track_file in all_track_files:
                        album_id = track_file.get("albumId")
                        date_added_str = track_file.get("dateAdded")
                        if not album_id or not date_added_str:
                            continue
                        try:
                            date_added = datetime.fromisoformat(date_added_str.replace('Z', '+00:00'))
                            if album_id not in trackfile_dates_by_album or date_added > trackfile_dates_by_album[album_id]:
                                trackfile_dates_by_album[album_id] = date_added
                        except Exception:
                            continue
                    
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
                        
                        most_recent = trackfile_dates_by_album.get(album_id)
                        if most_recent:
                            albums_with_dates.append((album, most_recent, album_mbid))
                    
                    albums_with_dates.sort(key=lambda x: x[1], reverse=True)
                    
                    for album, most_recent, album_mbid in albums_with_dates[:limit * 2]:
                        album_dates[album_mbid] = (int(most_recent.timestamp()), {
                            'album_data': album,
                            'artist_data': album.get("artist", {})
                        })
                    
                    logger.info(f"Total {len(album_dates)} unique albums after supplementing with track file dates")
                except Exception as e:
                    logger.warning(f"Failed to supplement with track file data: {e}")
            
            if not album_dates:
                logger.warning("No albums found with dates from either history or track files")
                return []
            
            sorted_albums = sorted(album_dates.items(), key=lambda x: x[1][0], reverse=True)
            recent_albums = sorted_albums[:limit]
            
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
                
                cover = None
                if imgs := album_data.get("images"):
                    first = imgs[0] if imgs else {}
                    cover = first.get("remoteUrl") or first.get("url")
                
                out.append(
                    LibraryAlbum(
                        artist=artist,
                        album=album_data.get("title"),
                        year=year,
                        monitored=album_data.get("monitored", False),
                        quality=None,
                        cover_url=cover,
                        musicbrainz_id=album_mbid,
                        artist_mbid=artist_mbid,
                        date_added=date_added,
                    )
                )
            
            logger.info(f"Retrieved {len(out)} recently added albums (merged from history and track files)")
            return out
            
        except Exception as e:
            logger.error(f"Failed to get recently imported albums: {e}")
            return []
    
    async def _get_recently_added_fallback(self, limit: int = 20) -> list[LibraryAlbum]:
        track_files = await self._get("/api/v1/trackfile")
        
        album_dates: dict[int, datetime] = {}
        for track_file in track_files:
            album_id = track_file.get("albumId")
            date_added_str = track_file.get("dateAdded")
            
            if not album_id or not date_added_str:
                continue
            
            try:
                date_added = datetime.fromisoformat(date_added_str.replace('Z', '+00:00'))
                if album_id not in album_dates or date_added < album_dates[album_id]:
                    album_dates[album_id] = date_added
            except Exception:
                continue
        
        if not album_dates:
            logger.warning("No track files with dateAdded found, cannot determine recently added albums")
            return []
        
        albums_data = await self._get("/api/v1/album")
        
        albums_with_dates = []
        for album in albums_data:
            if not album.get("monitored", False):
                continue
            
            album_id = album.get("id")
            if album_id in album_dates:
                albums_with_dates.append((album, album_dates[album_id]))
        
        albums_with_dates.sort(key=lambda x: x[1], reverse=True)
        recent_albums = albums_with_dates[:limit]
        
        out: list[LibraryAlbum] = []
        for item, date_added_dt in recent_albums:
            artist_data = item.get("artist", {})
            artist = artist_data.get("artistName", "Unknown")
            artist_mbid = artist_data.get("foreignArtistId")
            
            year = None
            if date := item.get("releaseDate"):
                try:
                    year = int(date.split("-")[0])
                except ValueError:
                    pass
            
            cover = None
            if imgs := item.get("images"):
                first = imgs[0] if imgs else {}
                cover = first.get("remoteUrl") or first.get("url")
            
            date_added = int(date_added_dt.timestamp())
            
            out.append(
                LibraryAlbum(
                    artist=artist,
                    album=item.get("title"),
                    year=year,
                    monitored=item.get("monitored", False),
                    quality=None,
                    cover_url=cover,
                    musicbrainz_id=item.get("foreignAlbumId"),
                    artist_mbid=artist_mbid,
                    date_added=date_added,
                )
            )
        
        logger.info(f"Retrieved {len(out)} recently added albums sorted by track file dateAdded (fallback)")
        return out
    
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/qualityprofile")
    
    async def get_metadata_profiles(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/metadataprofile")
    
    async def get_root_folders(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/rootfolder")

    def _build_api_media_cover_url(self, artist_id: int, url_path: str, size: Optional[int]) -> str:
        """Build API-authenticated URL for MediaCover.
        
        Lidarr's /MediaCover/ static endpoints don't accept API key auth,
        but /api/v1/MediaCover/artist/{id}/ does. This extracts the filename
        from the path and constructs the proper API URL.
        """
        path_part = url_path.split("?")[0]
        filename = path_part.rsplit("/", 1)[-1] if "/" in path_part else path_part
        
        if size and "." in filename:
            base, ext = filename.rsplit(".", 1)
            if not base.endswith(f"-{size}"):
                filename = f"{base}-{size}.{ext}"
        
        return f"{self._base_url}/api/v1/MediaCover/artist/{artist_id}/{filename}?apikey={self._settings.lidarr_api_key}"

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

    def _build_api_media_cover_url_album(self, album_id: int, url_path: str, size: Optional[int]) -> str:
        """Build API-authenticated URL for album MediaCover."""
        path_part = url_path.split("?")[0]
        filename = path_part.rsplit("/", 1)[-1] if "/" in path_part else path_part
        
        if size and "." in filename:
            base, ext = filename.rsplit(".", 1)
            if not base.endswith(f"-{size}"):
                filename = f"{base}-{size}.{ext}"
        
        return f"{self._base_url}/api/v1/MediaCover/album/{album_id}/{filename}?apikey={self._settings.lidarr_api_key}"

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
    async def get_artist_details(self, artist_mbid: str) -> Optional[dict[str, Any]]:
        """
        Fetch full artist details from Lidarr by MBID.
        
        Returns rich data including overview, genres, links, images, statistics.
        Returns None if artist is not in Lidarr.
        """
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
            
            images = artist.get("images", [])
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
                    constructed_url = self._build_api_media_cover_url(artist_id, url_path, 500)
                if cover_type == "poster" and not poster_url:
                    poster_url = constructed_url
                elif cover_type == "fanart" and not fanart_url:
                    fanart_url = constructed_url

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
                "poster_url": poster_url,
                "fanart_url": fanart_url,
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

    async def get_album_details(self, album_mbid: str) -> Optional[dict[str, Any]]:
        """
        Fetch full album details from Lidarr by MBID.
        
        Returns rich data including overview, genres, album type, tracks, links.
        Returns None if album is not in Lidarr.
        """
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
            
            images = album.get("images", [])
            cover_url = None
            for img in images:
                cover_type = img.get("coverType", "").lower()
                url_path = img.get("url", "")
                if not url_path:
                    continue
                if url_path.startswith("http"):
                    constructed_url = url_path
                else:
                    constructed_url = self._build_api_media_cover_url_album(album_id, url_path, 500)
                if cover_type == "cover":
                    cover_url = constructed_url
                    break
                elif not cover_url:
                    cover_url = constructed_url

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
        """
        Fetch track listing for an album from Lidarr by internal album ID.
        
        Returns list of tracks with position, title, duration.
        """
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

    async def get_artist_albums(self, artist_mbid: str) -> list[dict[str, Any]]:
        """
        Fetch all albums for an artist from Lidarr by artist MBID.
        
        Returns list of albums with basic info (for discography).
        """
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

                year = None
                if release_date := album.get("releaseDate"):
                    try:
                        year = int(release_date.split("-")[0])
                    except (ValueError, IndexError):
                        pass

                album_info = {
                    "id": album_id,
                    "title": album.get("title", "Unknown"),
                    "mbid": album.get("foreignAlbumId"),
                    "album_type": album.get("albumType"),
                    "secondary_types": album.get("secondaryTypes", []),
                    "release_date": album.get("releaseDate"),
                    "year": year,
                    "monitored": album.get("monitored", False),
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
import asyncio
import httpx
import logging
from typing import Any, Optional
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
    
    async def get_library(self) -> list[LibraryAlbum]:
        data = await self._get("/api/v1/album")
        out: list[LibraryAlbum] = []
        for item in data:
            artist = item.get("artist", {}).get("artistName", "Unknown")
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
            out.append(
                LibraryAlbum(
                    artist=artist,
                    album=item.get("title"),
                    year=year,
                    monitored=item.get("monitored", False),
                    quality=None,
                    cover_url=cover,
                )
            )
        return out
    
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
        """Add an album to Lidarr by MusicBrainz release group ID.
        
        Args:
            musicbrainz_id: MusicBrainz release group ID
            
        Returns:
            Dict with status message and response from Lidarr
        """
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
                            f"To fix this: Go to Lidarr → Settings → Profiles → Metadata Profiles, "
                            f"and enable '{album_type}' in your active profile."
                        )
                    else:
                        raise

        if not album_obj or "id" not in album_obj:
            raise ExternalServiceError(
                f"Cannot add this {album_type}. "
                f"'{album_title}' could not be found in Lidarr after the artist refresh. This usually means "
                f"your Lidarr Metadata Profile is configured to exclude {album_type}s. "
                f"To fix this: Go to Lidarr → Settings → Profiles → Metadata Profiles, "
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
        """Get an album from Lidarr by its foreign (MusicBrainz) ID."""
        try:
            items = await self._get("/api/v1/album", params={"foreignAlbumId": album_mbid})
            return items[0] if items else None
        except Exception as e:
            logger.warning(f"Error getting album by foreign ID {album_mbid}: {e}")
            return None
    
    async def _get_artist_by_id(self, artist_id: int) -> Optional[dict[str, Any]]:
        """Get an artist from Lidarr by ID."""
        try:
            return await self._get(f"/api/v1/artist/{artist_id}")
        except Exception as e:
            logger.warning(f"Error getting artist {artist_id}: {e}")
            return None
    
    async def _post_command(self, body: dict[str, Any]) -> Any:
        """Post a command to Lidarr and return the command object."""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/command",
                headers=self._get_headers(),
                json=body,
                timeout=120.0
            )
            if response.status_code not in (200, 201, 202):
                return None
            return response.json()
        except Exception:
            return None

    async def _get_command(self, cmd_id: int) -> Any:
        """Get the status of a command by its ID."""
        return await self._get(f"/api/v1/command/{cmd_id}")

    async def _await_command(self, body: dict[str, Any], timeout: float = 60.0, poll: float = 0.5) -> dict[str, Any] | None:
        """Post a command and wait for it to complete.
        
        Args:
            body: Command body to post
            timeout: Maximum time to wait for completion
            poll: Polling interval in seconds
            
        Returns:
            Final command status or None if failed
        """
        import time
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
        """Generic wait-for helper that polls until condition is met.
        
        Args:
            fetch_coro_factory: Async function that fetches the value to check
            stop: Function that returns True when condition is met
            timeout: Maximum time to wait
            poll: Polling interval
            
        Returns:
            Last fetched value
        """
        import time
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
        """Wait for all Lidarr commands related to an artist to complete.
        
        This is CRITICAL - we must wait for RefreshArtist and RescanArtist to finish
        before attempting to add albums, otherwise the album won't be indexed yet.
        
        Args:
            artist_id: Lidarr artist ID
            timeout: Maximum time to wait in seconds (default 10 minutes)
        """
        import time
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
        """Monitor both artist and album with retries.
        
        Args:
            artist_id: Lidarr artist ID
            album_id: Lidarr album ID
            album_mbid: MusicBrainz album ID
            album_title: Album title for logging
            max_attempts: Maximum number of retry attempts
        """
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
        """Ensure an artist exists in Lidarr, adding if necessary and waiting for full refresh.
        
        This method will:
        1. Check if artist already exists
        2. If not, create the artist with minimal monitoring
        3. Trigger RefreshArtist and RescanArtist commands
        4. WAIT for those commands to complete (this can take several minutes!)
        5. Return the artist object
        
        Args:
            artist_mbid: MusicBrainz artist ID
            artist_name_hint: Optional artist name hint for display
            
        Returns:
            Artist object from Lidarr
        """
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

from typing import Any
import asyncio
import time

import httpx

from config_manager import CONFIG
from models import LibraryAlbum, QueueItem, ServiceStatus
from utils.common import ApiError, get_auth_headers
from utils.cache import get_cache

BASE_URL = CONFIG["lidarr_url"].rstrip("/")
_cache = get_cache()

_lidarr_client: httpx.AsyncClient | None = None


def _get_lidarr_client() -> httpx.AsyncClient:
    global _lidarr_client
    if _lidarr_client is None:
        _lidarr_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,
            ),
            http2=True,
        )
    return _lidarr_client


async def _get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{BASE_URL}{endpoint}"
    client = _get_lidarr_client()
    r = await client.get(url, headers=get_auth_headers(), params=params)
    if r.status_code != 200:
        raise ApiError(f"Lidarr GET failed ({r.status_code})", r.text)
    return r.json()


async def _post(endpoint: str, data: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{endpoint}"
    client = _get_lidarr_client()
    r = await client.post(url, headers=get_auth_headers(), json=data)
    if r.status_code not in (200, 201, 202):
        raise ApiError(f"Lidarr POST failed ({r.status_code})", r.text)
    return r.json()


async def _put(endpoint: str, data: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{endpoint}"
    client = _get_lidarr_client()
    r = await client.put(url, headers=get_auth_headers(), json=data)
    if r.status_code not in (200, 202):
        raise ApiError(f"Lidarr PUT failed ({r.status_code})", r.text)
    try:
        return r.json()
    except ValueError:
        return None


async def get_status() -> ServiceStatus:
    try:
        data = await _get("/api/v1/system/status")
        return ServiceStatus(status="ok", version=data.get("version"))
    except Exception as e:
        return ServiceStatus(status="error", message=str(e))


async def get_library() -> list[LibraryAlbum]:
    data = await _get("/api/v1/album")
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


async def get_library_grouped() -> list[dict[str, Any]]:
    data = await _get("/api/v1/album")
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


async def get_library_mbids(include_release_ids: bool = True) -> set[str]:
    cache_key = f"library_mbids:{include_release_ids}"
    
    cached_result = await _cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    data = await _get("/api/v1/album")
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
    
    await _cache.set(cache_key, ids, ttl_seconds=60)
    return ids


async def get_artist_mbids() -> set[str]:
    cache_key = "artist_mbids"
    
    cached_result = await _cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    data = await _get("/api/v1/artist")
    ids: set[str] = set()
    for item in data:
        if not item.get("monitored", False):
            continue
        mbid = item.get("foreignArtistId") or item.get("mbId")
        if isinstance(mbid, str):
            ids.add(mbid.lower())
    
    await _cache.set(cache_key, ids, ttl_seconds=60)
    return ids


async def get_queue() -> list[QueueItem]:
    data = await _get("/api/v1/queue")
    items = data.get("records", []) if isinstance(data, dict) else data
    out: list[QueueItem] = []
    for item in items:
        size, sizeleft = item.get("size"), item.get("sizeleft")
        progress = None
        if size and sizeleft:
            try:
                progress = int(100 - (sizeleft / size * 100))
            except Exception:
                progress = None
        out.append(
            QueueItem(
                artist=item.get("artist", {}).get("artistName", "Unknown"),
                album=item.get("title"),
                status=item.get("status", "unknown"),
                progress=progress,
                eta=None,
            )
        )
    return out


async def lookup_album(term: str) -> list[dict[str, Any]]:
    return await _get("/api/v1/album/lookup", params={"term": "mbid:" + term})


async def _list_rootfolders() -> list[dict[str, Any]]:
    return await _get("/api/v1/rootfolder")


async def _list_quality_profiles() -> list[dict[str, Any]]:
    return await _get("/api/v1/qualityprofile")


async def _list_metadata_profiles() -> list[dict[str, Any]]:
    return await _get("/api/v1/metadataprofile")


async def _find_artist_by_mbid(artist_mbid: str) -> dict[str, Any] | None:
    items = await _get("/api/v1/artist", params={"mbId": artist_mbid})
    return items[0] if items else None


async def _lookup_artist_by_mbid(artist_mbid: str) -> dict[str, Any] | None:
    items = await _get("/api/v1/artist/lookup", params={"term": f"mbid:{artist_mbid}"})
    return items[0] if items else None


async def _post_command(body: dict[str, Any]) -> Any:
    url = f"{BASE_URL}/api/v1/command"
    client = _get_lidarr_client()
    r = await client.post(
        url, 
        headers=get_auth_headers(), 
        json=body,
        timeout=120.0
    )
    if r.status_code not in (200, 201, 202):
        return None
    return r.json()


async def _get_command(cmd_id: int) -> Any:
    return await _get(f"/api/v1/command/{cmd_id}")


async def _await_command(body: dict[str, Any], timeout: float = 60.0, poll: float = 0.5) -> dict[str, Any] | None:
    try:
        cmd = await _post_command(body)
        if not cmd or "id" not in cmd:
            await asyncio.sleep(min(timeout, 5.0))
            return None
        cmd_id = cmd["id"]
        deadline = time.monotonic() + timeout
        last_status = None
        while time.monotonic() < deadline:
            await asyncio.sleep(poll)
            try:
                status = await _get_command(cmd_id)
                last_status = status
            except Exception:
                continue
            state = (status or {}).get("status") or (status or {}).get("state")
            if str(state).lower() in {"completed", "failed", "aborted", "cancelled"}:
                return status
        return last_status
    except Exception:
        return None


async def _get_album_by_foreign_id(album_mbid: str) -> dict[str, Any] | None:
    items = await _get("/api/v1/album", params={"foreignAlbumId": album_mbid})
    return items[0] if items else None


async def _get_artist_by_id(artist_id: int) -> dict[str, Any] | None:
    return await _get(f"/api/v1/artist/{artist_id}")


async def _ensure_artist(artist_mbid: str, artist_name_hint: str | None = None) -> dict[str, Any]:
    if existing := await _find_artist_by_mbid(artist_mbid):
        return existing

    roots = await _list_rootfolders()
    if not roots:
        raise ApiError(
            "No root folders configured in Lidarr.", "Configure a root folder in Lidarr first."
        )
    root = next((r for r in roots if r.get("accessible", True)), roots[0])

    qp_id = root.get("defaultQualityProfileId")
    mp_id = root.get("defaultMetadataProfileId")
    if qp_id is None:
        qps = await _list_quality_profiles()
        if not qps:
            raise ApiError("No quality profiles in Lidarr.", "Create at least one quality profile.")
        qp_id = qps[0]["id"]
    if mp_id is None:
        mps = await _list_metadata_profiles()
        if not mps:
            raise ApiError(
                "No metadata profiles in Lidarr.", "Create at least one metadata profile."
            )
        mp_id = mps[0]["id"]

    remote = await _lookup_artist_by_mbid(artist_mbid)
    artist_name = (remote or {}).get("artistName") or artist_name_hint or "Unknown Artist"

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
    created = await _post("/api/v1/artist", payload)

    await _await_command({"name": "RefreshArtist", "artistId": created["id"]}, timeout=600.0)
    await _await_command({"name": "RescanArtist", "artistId": created["id"]}, timeout=300.0)
    
    await asyncio.sleep(5.0)

    return created


async def _wait_for(
    fetch_coro_factory, stop=lambda v: bool(v), timeout: float = 30.0, poll: float = 0.5
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


async def _wait_for_artist_commands_to_complete(artist_id: int, timeout: float = 600.0) -> None:
    async def no_artist_commands_running():
        commands = await _get("/api/v1/command")
        if not commands:
            return True
        
        for cmd in commands:
            if cmd.get("status") in ["queued", "started"]:
                body = cmd.get("body", {})
                if body.get("artistId") == artist_id or body.get("artistIds") == [artist_id]:
                    return False
        return True
    
    await _wait_for(no_artist_commands_running, timeout=timeout, poll=5.0)
    await asyncio.sleep(5.0)


async def _monitor_artist_and_album(
    artist_id: int, 
    album_id: int, 
    album_mbid: str, 
    album_title: str,
    max_attempts: int = 3
) -> None:
    for attempt in range(max_attempts):
        try:
            await _put(
                "/api/v1/artist/editor",
                {"artistIds": [artist_id], "monitored": True, "monitorNewItems": "none"},
            )
            
            await asyncio.sleep(5.0 + (attempt * 3.0))
            
            await _put("/api/v1/album/monitor", {"albumIds": [album_id], "monitored": True})
            
            async def both_monitored():
                album = await _get_album_by_foreign_id(album_mbid)
                artist = await _get_artist_by_id(artist_id)
                return (album and album.get("monitored")) and (artist and artist.get("monitored"))
            
            timeout = 20.0 + (attempt * 10.0)
            if await _wait_for(both_monitored, timeout=timeout, poll=1.0):
                return
                
            if attempt < max_attempts - 1:
                await asyncio.sleep(5.0)
                
        except Exception as e:
            if attempt == max_attempts - 1:
                raise ApiError(
                    "Failed to set monitoring status",
                    f"Could not ensure '{album_title}' is monitored after {max_attempts} attempts: {str(e)}"
                )
            await asyncio.sleep(5.0)


async def add_album(album_mbid: str) -> dict[str, Any]:
    if not album_mbid or not isinstance(album_mbid, str):
        raise ApiError("Invalid MBID.", "Provide a MusicBrainz release-group MBID string.")

    lookup = await _get("/api/v1/album/lookup", params={"term": f"mbid:{album_mbid}"})
    if not lookup:
        raise ApiError(
            "Release not found.", 
            f"Lidarr couldn't find this release (MBID: {album_mbid}). This might be a very obscure release that's not in MusicBrainz, or there's a connectivity issue."
        )
    
    candidate = next((a for a in lookup if a.get("foreignAlbumId") == album_mbid), lookup[0])
    album_title = candidate.get("title") or "Unknown Album"
    album_type = candidate.get("albumType", "Unknown")
    secondary_types = candidate.get("secondaryTypes", [])
    
    artist_info = candidate.get("artist") or {}
    artist_mbid = artist_info.get("mbId") or artist_info.get("foreignArtistId")
    artist_name = artist_info.get("artistName")
    if not artist_mbid:
        raise ApiError(
            "Missing artist MBID in lookup result.", "Album lookup didn't include an artist MBID."
        )

    artist = await _ensure_artist(artist_mbid, artist_name)
    artist_id = artist["id"]

    album_obj = await _get_album_by_foreign_id(album_mbid)
    action = "exists"
    
    if not album_obj:
        async def album_is_indexed():
            a = await _get_album_by_foreign_id(album_mbid)
            return a and a.get("id") and a.get("releases")
        
        album_obj = await _wait_for(album_is_indexed, timeout=60.0, poll=3.0)
        
        if not album_obj:
            profile_id = artist.get("qualityProfileId")
            if profile_id is None:
                qps = await _list_quality_profiles()
                if not qps:
                    raise ApiError(
                        "No quality profiles in Lidarr.", "Create at least one quality profile."
                    )
                profile_id = qps[0]["id"]

            payload = {
                "title": album_title,
                "artistId": artist_id,
                "foreignAlbumId": album_mbid,
                "monitored": True,
                "anyReleaseOk": True,
                "profileId": profile_id,
                "addOptions": {"addType": "automatic", "searchForNewAlbum": True},
            }
            
            try:
                album_obj = await _post("/api/v1/album", payload)
                action = "added"
                album_obj = await _wait_for(album_is_indexed, timeout=120.0, poll=2.0)
            except ApiError as e:
                if "POST failed" in str(e.message):
                    raise ApiError(
                        f"Cannot add this {album_type}.",
                        f"Lidarr rejected adding '{album_title}'. This is likely because your Lidarr "
                        f"Metadata Profile is configured to exclude {album_type}s{' (' + ', '.join(secondary_types) + ')' if secondary_types else ''}. "
                        f"To fix this: Go to Lidarr → Settings → Profiles → Metadata Profiles, "
                        f"and enable '{album_type}' in your active profile."
                    )
                else:
                    raise

    if not album_obj or "id" not in album_obj:
        raise ApiError(
            f"Cannot add this {album_type}.", 
            f"'{album_title}' could not be found in Lidarr after the artist refresh. This usually means "
            f"your Lidarr Metadata Profile is configured to exclude {album_type}s. "
            f"To fix this: Go to Lidarr → Settings → Profiles → Metadata Profiles, "
            f"enable '{album_type}', then refresh the artist in Lidarr."
        )

    album_id = album_obj["id"]
    
    await _wait_for_artist_commands_to_complete(artist_id, timeout=600.0)

    await _monitor_artist_and_album(artist_id, album_id, album_mbid, album_title)

    try:
        await _post_command({"name": "AlbumSearch", "albumIds": [album_id]})
    except Exception:
        pass

    final_album = await _get_album_by_foreign_id(album_mbid)
    
    if final_album and not final_album.get("monitored"):
        try:
            await _put("/api/v1/album/monitor", {"albumIds": [album_id], "monitored": True})
            await asyncio.sleep(2.0)
            final_album = await _get_album_by_foreign_id(album_mbid)
        except Exception:
            pass
    
    msg = "Album added & monitored" if action == "added" else "Album exists; monitored ensured"
    return {"message": f"{msg}: {album_title}", "payload": final_album}

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


async def _get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=get_auth_headers(), params=params)
        if r.status_code != 200:
            raise ApiError(f"Lidarr GET failed ({r.status_code})", r.text)
        return r.json()


async def _post(endpoint: str, data: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=get_auth_headers(), json=data)
        if r.status_code not in (200, 201, 202):
            raise ApiError(f"Lidarr POST failed ({r.status_code})", r.text)
        return r.json()


async def _put(endpoint: str, data: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=60.0) as client:
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
        # Only include albums that are monitored
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
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=get_auth_headers(), json=body)
        if r.status_code not in (200, 201, 202):
            print("[WARN] command failed:", r.text[:300])
            return None
        return r.json()


async def _get_command(cmd_id: int) -> Any:
    return await _get(f"/api/v1/command/{cmd_id}")


async def _await_command(body: dict[str, Any], timeout: float = 60.0, poll: float = 0.5) -> None:
    try:
        cmd = await _post_command(body)
        if not cmd or "id" not in cmd:
            await asyncio.sleep(min(timeout, 5.0))
            return
        cmd_id = cmd["id"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(poll)
            try:
                status = await _get_command(cmd_id)
            except Exception:
                continue
            state = (status or {}).get("status") or (status or {}).get("state")
            if str(state).lower() in {"completed", "failed", "aborted", "cancelled"}:
                return
    except Exception:
        pass


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

    await _await_command({"name": "RefreshArtist", "artistId": created["id"]})
    await _await_command({"name": "RescanArtist", "artistId": created["id"]})

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


async def add_album(album_mbid: str) -> dict[str, Any]:
    if not album_mbid or not isinstance(album_mbid, str):
        raise ApiError("Invalid MBID.", "Provide a MusicBrainz release-group MBID string.")

    lookup = await _get("/api/v1/album/lookup", params={"term": f"mbid:{album_mbid}"})
    if not lookup:
        raise ApiError("Album not found from MBID.", f"No lookup result for {album_mbid}")
    candidate = next((a for a in lookup if a.get("foreignAlbumId") == album_mbid), lookup[0])
    album_title = candidate.get("title") or "Unknown Album"
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
        album_obj = await _post("/api/v1/album", payload)
        action = "added"


    album_obj = await _wait_for(
        lambda: _get_album_by_foreign_id(album_mbid), stop=lambda a: a and a.get("id"), timeout=45.0
    )
    if not album_obj or "id" not in album_obj:
        await _put(
            "/api/v1/artist/editor",
            {"artistIds": [artist_id], "monitored": True, "monitorNewItems": "none"},
        )
        raise ApiError(
            "Album not visible after add.", "Timed out waiting for album to index/hydrate."
        )

    album_id = album_obj["id"]

    await _put(
        "/api/v1/artist/editor",
        {"artistIds": [artist_id], "monitored": True, "monitorNewItems": "none"},
    )
    await _put("/api/v1/album/monitor", {"albumIds": [album_id], "monitored": True})

    try:
        await _post_command({"name": "AlbumSearch", "albumIds": [album_id]})
    except Exception:
        pass

    async def both_monitored():
        a = await _get_album_by_foreign_id(album_mbid)
        art = await _get_artist_by_id(artist_id)
        return (a and a.get("monitored") is True) and (art and art.get("monitored") is True)

    ok = await _wait_for(both_monitored, timeout=20.0, poll=0.5)
    if not ok:
        await _put(
            "/api/v1/artist/editor",
            {"artistIds": [artist_id], "monitored": True, "monitorNewItems": "none"},
        )
        await _put("/api/v1/album/monitor", {"albumIds": [album_id], "monitored": True})
        await _wait_for(both_monitored, timeout=10.0, poll=0.5)

    final_album = await _get_album_by_foreign_id(album_mbid)
    msg = "Album added & monitored" if action == "added" else "Album exists; monitored ensured"
    return {"message": f"{msg}: {album_title}", "payload": final_album}

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
import msgspec

from core.exceptions import ExternalServiceError, NavidromeApiError, NavidromeAuthError, NavidromeSubsonicError
from infrastructure.cache.cache_keys import NAVIDROME_PREFIX
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from repositories.navidrome_models import (
    StreamProxyResult as StreamProxyResult,
    SubsonicAlbum,
    SubsonicArtist,
    SubsonicGenre,
    SubsonicPlaylist,
    SubsonicSearchResult,
    SubsonicSong,
    parse_album,
    parse_artist,
    parse_genre,
    parse_song,
    parse_subsonic_response,
)
from infrastructure.degradation import try_get_degradation_context
from infrastructure.integration_result import IntegrationResult

logger = logging.getLogger(__name__)

_SOURCE = "navidrome"


def _record_degradation(msg: str) -> None:
    ctx = try_get_degradation_context()
    if ctx is not None:
        ctx.record(IntegrationResult.error(source=_SOURCE, msg=msg))

_navidrome_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="navidrome",
)

_DEFAULT_TTL_LIST = 300
_DEFAULT_TTL_SEARCH = 120
_DEFAULT_TTL_GENRES = 3600
_DEFAULT_TTL_DETAIL = 300


class NavidromeRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
    ) -> None:
        self._client = http_client
        self._cache = cache
        self._url: str = ""
        self._username: str = ""
        self._password: str = ""
        self._configured: bool = False
        self._ttl_list: int = _DEFAULT_TTL_LIST
        self._ttl_search: int = _DEFAULT_TTL_SEARCH
        self._ttl_genres: int = _DEFAULT_TTL_GENRES
        self._ttl_detail: int = _DEFAULT_TTL_DETAIL

    def configure(self, url: str, username: str, password: str) -> None:
        self._url = url.rstrip("/") if url else ""
        self._username = username
        self._password = password
        self._configured = bool(self._url and self._username and self._password)

    def is_configured(self) -> bool:
        return self._configured

    def configure_cache_ttls(
        self,
        *,
        list_ttl: int | None = None,
        search_ttl: int | None = None,
        genres_ttl: int | None = None,
        detail_ttl: int | None = None,
    ) -> None:
        if list_ttl is not None:
            self._ttl_list = list_ttl
        if search_ttl is not None:
            self._ttl_search = search_ttl
        if genres_ttl is not None:
            self._ttl_genres = genres_ttl
        if detail_ttl is not None:
            self._ttl_detail = detail_ttl

    @staticmethod
    def reset_circuit_breaker() -> None:
        _navidrome_circuit_breaker.reset()

    def _build_auth_params(self) -> dict[str, str]:
        salt = secrets.token_hex(3)
        token = hashlib.md5(
            (self._password + salt).encode("utf-8")
        ).hexdigest()
        return {
            "u": self._username,
            "t": token,
            "s": salt,
            "v": "1.16.1",
            "c": "musicseerr",
            "f": "json",
        }

    def build_stream_url(self, song_id: str) -> str:
        """Build a full stream URL for a song, including auth params."""
        if not self._configured:
            raise ValueError("Navidrome is not configured")
        params = self._build_auth_params()
        params["id"] = song_id
        return f"{self._url}/rest/stream?{urlencode(params)}"

    async def proxy_head_stream(self, song_id: str) -> StreamProxyResult:
        """HEAD proxy to Navidrome stream endpoint. Returns filtered headers."""
        stream_url = self.build_stream_url(song_id)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=10, write=10, pool=10)
        ) as client:
            try:
                resp = await client.head(stream_url)
            except httpx.HTTPError:
                raise ExternalServiceError("Failed to reach Navidrome")

        headers: dict[str, str] = {}
        for h in _PROXY_FORWARD_HEADERS:
            v = resp.headers.get(h)
            if v:
                headers[h] = v
        return StreamProxyResult(
            status_code=resp.status_code,
            headers=headers,
            media_type=headers.get("Content-Type", "audio/mpeg"),
        )

    async def proxy_get_stream(
        self, song_id: str, range_header: str | None = None
    ) -> StreamProxyResult:
        """GET streaming proxy to Navidrome. Returns chunked body iterator with cleanup."""
        stream_url = self.build_stream_url(song_id)

        upstream_headers: dict[str, str] = {}
        if range_header:
            upstream_headers["Range"] = range_header

        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)
        )
        upstream_resp = None
        try:
            upstream_resp = await client.send(
                client.build_request("GET", stream_url, headers=upstream_headers),
                stream=True,
            )

            if upstream_resp.status_code == 416:
                raise ExternalServiceError("416 Range not satisfiable")

            if upstream_resp.status_code >= 400:
                logger.error(
                    "Navidrome upstream returned %d for %s",
                    upstream_resp.status_code, song_id,
                )
                raise ExternalServiceError("Navidrome returned an error")

            resp_headers: dict[str, str] = {}
            for header_name in _PROXY_FORWARD_HEADERS:
                value = upstream_resp.headers.get(header_name)
                if value:
                    resp_headers[header_name] = value

            status_code = 206 if upstream_resp.status_code == 206 else 200

            async def _stream_body() -> AsyncIterator[bytes]:
                try:
                    async for chunk in upstream_resp.aiter_bytes(
                        chunk_size=_STREAM_CHUNK_SIZE
                    ):
                        yield chunk
                finally:
                    await upstream_resp.aclose()
                    await client.aclose()

            return StreamProxyResult(
                status_code=status_code,
                headers=resp_headers,
                media_type=resp_headers.get("Content-Type", "audio/mpeg"),
                body_chunks=_stream_body(),
            )
        except Exception:
            if upstream_resp:
                await upstream_resp.aclose()
            await client.aclose()
            raise

    @with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        circuit_breaker=_navidrome_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError, ExternalServiceError),
        non_breaking_exceptions=(NavidromeSubsonicError,),
    )
    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._configured:
            raise ExternalServiceError("Navidrome not configured")

        merged = self._build_auth_params()
        if params:
            merged.update(params)

        url = f"{self._url}{endpoint}"
        try:
            response = await self._client.get(url, params=merged, timeout=15.0)
        except httpx.TimeoutException as exc:
            raise ExternalServiceError(f"Navidrome request timed out: {exc}")
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Navidrome request failed: {exc}")

        if response.status_code in (401, 403):
            raise NavidromeAuthError(
                f"Navidrome authentication failed ({response.status_code})"
            )
        if response.status_code != 200:
            raise NavidromeApiError(
                f"Navidrome request failed ({response.status_code})",
            )

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise NavidromeApiError(f"Navidrome returned invalid JSON for {endpoint}") from exc
        return parse_subsonic_response(data)

    async def ping(self) -> bool:
        try:
            await self._request("/rest/ping")
            return True
        except Exception:  # noqa: BLE001
            _record_degradation("Navidrome ping failed")
            return False

    async def get_album_list(
        self,
        type: str,
        size: int = 20,
        offset: int = 0,
        genre: str | None = None,
    ) -> list[SubsonicAlbum]:
        cache_key = f"{NAVIDROME_PREFIX}albums:{type}:{size}:{offset}:{genre or ''}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, Any] = {"type": type, "size": size, "offset": offset}
        if genre and type == "byGenre":
            params["genre"] = genre
        resp = await self._request(
            "/rest/getAlbumList2",
            params,
        )
        raw = resp.get("albumList2", {}).get("album", [])
        albums = [parse_album(a) for a in raw]
        await self._cache.set(cache_key, albums, self._ttl_list)
        return albums

    async def get_album(self, id: str) -> SubsonicAlbum:
        cache_key = f"{NAVIDROME_PREFIX}album:{id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getAlbum", {"id": id})
        album = parse_album(resp.get("album", {}))
        await self._cache.set(cache_key, album, self._ttl_detail)
        return album

    async def get_artists(self) -> list[SubsonicArtist]:
        cache_key = "navidrome:artists"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getArtists")
        artists: list[SubsonicArtist] = []
        for index in resp.get("artists", {}).get("index", []):
            for a in index.get("artist", []):
                artists.append(parse_artist(a))
        await self._cache.set(cache_key, artists, self._ttl_list)
        return artists

    async def get_artist(self, id: str) -> SubsonicArtist:
        cache_key = f"{NAVIDROME_PREFIX}artist:{id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getArtist", {"id": id})
        artist = parse_artist(resp.get("artist", {}))
        await self._cache.set(cache_key, artist, self._ttl_detail)
        return artist

    async def get_song(self, id: str) -> SubsonicSong:
        cache_key = f"{NAVIDROME_PREFIX}song:{id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getSong", {"id": id})
        song = parse_song(resp.get("song", {}))
        await self._cache.set(cache_key, song, self._ttl_detail)
        return song

    async def search(
        self,
        query: str,
        artist_count: int = 20,
        album_count: int = 20,
        song_count: int = 20,
    ) -> SubsonicSearchResult:
        cache_key = f"{NAVIDROME_PREFIX}search:{query}:{artist_count}:{album_count}:{song_count}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request(
            "/rest/search3",
            {
                "query": query,
                "artistCount": artist_count,
                "albumCount": album_count,
                "songCount": song_count,
            },
        )
        sr = resp.get("searchResult3", {})
        result = SubsonicSearchResult(
            artist=[parse_artist(a) for a in sr.get("artist", [])],
            album=[parse_album(a) for a in sr.get("album", [])],
            song=[parse_song(s) for s in sr.get("song", [])],
        )
        await self._cache.set(cache_key, result, self._ttl_search)
        return result

    async def get_starred(self) -> SubsonicSearchResult:
        cache_key = "navidrome:starred"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getStarred2")
        sr = resp.get("starred2", {})
        result = SubsonicSearchResult(
            artist=[parse_artist(a) for a in sr.get("artist", [])],
            album=[parse_album(a) for a in sr.get("album", [])],
            song=[parse_song(s) for s in sr.get("song", [])],
        )
        await self._cache.set(cache_key, result, self._ttl_list)
        return result

    async def get_genres(self) -> list[SubsonicGenre]:
        cache_key = "navidrome:genres"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getGenres")
        raw = resp.get("genres", {}).get("genre", [])
        genres = [parse_genre(g) for g in raw]
        await self._cache.set(cache_key, genres, self._ttl_genres)
        return genres

    async def get_playlists(self) -> list[SubsonicPlaylist]:
        cache_key = "navidrome:playlists"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getPlaylists")
        raw = resp.get("playlists", {}).get("playlist", [])
        playlists: list[SubsonicPlaylist] = []
        for p in raw:
            playlists.append(
                SubsonicPlaylist(
                    id=p.get("id", ""),
                    name=p.get("name", ""),
                    songCount=p.get("songCount", 0),
                    duration=p.get("duration", 0),
                )
            )
        await self._cache.set(cache_key, playlists, self._ttl_list)
        return playlists

    async def get_playlist(self, id: str) -> SubsonicPlaylist:
        cache_key = f"{NAVIDROME_PREFIX}playlist:{id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = await self._request("/rest/getPlaylist", {"id": id})
        raw = resp.get("playlist", {})
        entries = raw.get("entry", [])
        playlist = SubsonicPlaylist(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            songCount=raw.get("songCount", 0),
            duration=raw.get("duration", 0),
            entry=[parse_song(e) for e in entries] if entries else None,
        )
        await self._cache.set(cache_key, playlist, self._ttl_detail)
        return playlist

    async def get_random_songs(
        self,
        size: int = 20,
        genre: str | None = None,
    ) -> list[SubsonicSong]:
        params: dict[str, Any] = {"size": size}
        if genre:
            params["genre"] = genre

        resp = await self._request("/rest/getRandomSongs", params)
        raw = resp.get("randomSongs", {}).get("song", [])
        return [parse_song(s) for s in raw]

    async def scrobble(
        self,
        id: str,
        time_ms: int | None = None,
    ) -> bool:
        params: dict[str, Any] = {"id": id}
        if time_ms is not None:
            params["time"] = time_ms

        try:
            await self._request("/rest/scrobble", params)
            return True
        except Exception:  # noqa: BLE001
            _record_degradation("Navidrome scrobble failed")
            return False

    async def now_playing(self, id: str) -> bool:
        params: dict[str, Any] = {"id": id, "submission": "false"}
        try:
            await self._request("/rest/scrobble", params)
            return True
        except Exception:  # noqa: BLE001
            _record_degradation("Navidrome now-playing report failed")
            return False

    async def validate_connection(self) -> tuple[bool, str]:
        if not self._configured:
            return False, "Navidrome URL, username, or password not configured"

        try:
            resp = await self._request("/rest/ping")
            version = resp.get("version", "unknown")
            return True, f"Connected to Navidrome (API v{version})"
        except NavidromeAuthError as exc:
            return False, f"Authentication failed: {exc.message}"
        except ExternalServiceError as exc:
            msg = str(exc)
            if "timed out" in msg.lower():
                return False, "Connection timed out - check URL"
            if "connect" in msg.lower() or "refused" in msg.lower():
                return False, "Could not connect - check URL and ensure server is running"
            return False, f"Connection failed: {msg}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Connection failed: {exc}"

    async def clear_cache(self) -> None:
        await self._cache.clear_prefix(NAVIDROME_PREFIX)

    async def get_cover_art(self, cover_art_id: str, size: int = 500) -> tuple[bytes, str]:
        if not self._configured:
            raise ExternalServiceError("Navidrome not configured")

        params = self._build_auth_params()
        params["id"] = cover_art_id
        params["size"] = str(size)

        url = f"{self._url}/rest/getCoverArt"
        try:
            response = await self._client.get(url, params=params, timeout=15.0)
        except httpx.TimeoutException:
            raise ExternalServiceError("Navidrome cover art request timed out")
        except httpx.HTTPError:
            raise ExternalServiceError("Navidrome cover art request failed")

        if response.status_code != 200:
            raise ExternalServiceError(
                f"Navidrome cover art failed ({response.status_code})"
            )

        content_type = response.headers.get("content-type", "image/jpeg")
        return response.content, content_type


_PROXY_FORWARD_HEADERS = {"Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"}
_STREAM_CHUNK_SIZE = 64 * 1024

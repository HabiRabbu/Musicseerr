import httpx
import logging
from typing import Any

import msgspec
from core.exceptions import ExternalServiceError, ResourceNotFoundError
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.persistent_cache import LibraryCache
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from repositories.jellyfin_models import JellyfinItem, JellyfinUser, parse_item, parse_user

logger = logging.getLogger(__name__)

_jellyfin_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="jellyfin"
)

JellyfinJsonObject = dict[str, Any]
JellyfinJsonArray = list[JellyfinJsonObject]
JellyfinJson = JellyfinJsonObject | JellyfinJsonArray


def _decode_json_response(response: httpx.Response) -> JellyfinJson:
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray, memoryview)):
        return msgspec.json.decode(content, type=JellyfinJson)
    return response.json()


class JellyfinRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
        base_url: str = "",
        api_key: str = "",
        user_id: str = "",
        library_cache: LibraryCache | None = None,
    ):
        self._client = http_client
        self._cache = cache
        self._library_cache = library_cache
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._user_id = user_id
    
    def configure(self, base_url: str, api_key: str, user_id: str = "") -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._user_id = user_id
    
    @staticmethod
    def reset_circuit_breaker() -> None:
        _jellyfin_circuit_breaker.reset()
    
    def is_configured(self) -> bool:
        return bool(self._base_url and self._api_key)
    
    def _get_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Emby-Token": self._api_key,
        }
    
    @with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        circuit_breaker=_jellyfin_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError, ExternalServiceError)
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        if not self._base_url or not self._api_key:
            raise ExternalServiceError("Jellyfin not configured")
        
        url = f"{self._base_url}{endpoint}"
        
        try:
            response = await self._client.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
                timeout=15.0,
            )
            
            if response.status_code == 401:
                raise ExternalServiceError("Jellyfin authentication failed - check API key")
            
            if response.status_code == 404:
                return None
            
            if response.status_code not in (200, 204):
                raise ExternalServiceError(
                    f"Jellyfin {method} failed ({response.status_code})",
                    response.text
                )
            
            if response.status_code == 204:
                return None
            
            try:
                return _decode_json_response(response)
            except (msgspec.DecodeError, ValueError, TypeError):
                return None
        
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"Jellyfin request failed: {str(e)}")
    
    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> Any:
        return await self._request("GET", endpoint, params=params)
    
    async def validate_connection(self) -> tuple[bool, str]:
        if not self._base_url or not self._api_key:
            return False, "Jellyfin URL or API key not configured"
        
        try:
            url = f"{self._base_url}/System/Info"
            response = await self._client.request(
                "GET",
                url,
                headers=self._get_headers(),
                timeout=10.0,
            )
            
            if response.status_code == 401:
                return False, "Authentication failed - check API key"
            
            if response.status_code != 200:
                return False, f"Connection failed (HTTP {response.status_code})"
            
            result = _decode_json_response(response)
            server_name = result.get("ServerName", "Unknown")
            version = result.get("Version", "Unknown")
            return True, f"Connected to {server_name} (v{version})"
        except httpx.TimeoutException:
            return False, "Connection timed out - check URL"
        except httpx.ConnectError:
            return False, "Could not connect - check URL and ensure server is running"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    async def get_users(self) -> list[JellyfinUser]:
        try:
            result = await self._get("/Users")
            if not result:
                return []
            return [parse_user(user) for user in result if user.get("Id")]
        except Exception as e:
            logger.error(f"Failed to get Jellyfin users: {e}")
            return []

    async def fetch_users_direct(self) -> list[JellyfinUser]:
        if not self._base_url or not self._api_key:
            return []
        
        try:
            url = f"{self._base_url}/Users"
            response = await self._client.request(
                "GET",
                url,
                headers=self._get_headers(),
                timeout=10.0,
            )
            
            if response.status_code != 200:
                return []
            
            result = _decode_json_response(response)
            if not result:
                return []
            return [parse_user(user) for user in result if user.get("Id")]
        except Exception as e:
            logger.error(f"Failed to fetch Jellyfin users: {e}")
            return []

    async def get_current_user(self) -> JellyfinUser | None:
        try:
            result = await self._get("/Users/Me")
            return parse_user(result) if result else None
        except Exception:
            return None

    async def _fetch_items(
        self,
        endpoint: str,
        cache_key: str,
        params: dict[str, Any],
        error_msg: str,
        ttl: int = 300,
        filter_fn=None,
        raise_on_error: bool = False,
    ) -> list[JellyfinItem]:
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        try:
            result = await self._get(endpoint, params=params)
            if not result:
                if raise_on_error:
                    raise ExternalServiceError(f"{error_msg}: empty response from Jellyfin")
                logger.warning(f"{error_msg}: _get returned None/empty")
                return []
            raw_items = result.get("Items", []) if isinstance(result, dict) else result
            items = [parse_item(i) for i in raw_items if not filter_fn or filter_fn(i)]
            if items:
                await self._cache.set(cache_key, items, ttl_seconds=ttl)
            return items
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"{error_msg}: {e}")
            if raise_on_error:
                raise ExternalServiceError(f"{error_msg}: {e}") from e
            return []

    async def get_recently_played(
        self,
        user_id: str | None = None,
        limit: int = 20,
        ttl_seconds: int = 300,
    ) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "includeItemTypes": "Audio", "sortBy": "DatePlayed",
                  "sortOrder": "Descending", "isPlayed": "true", "enableUserData": "true",
                  "limit": limit, "recursive": "true", "Fields": "ProviderIds"}
        return await self._fetch_items(
            "/Items",
            f"jellyfin_recent:{uid}:{limit}",
            params,
            "Failed to get recently played",
            ttl=ttl_seconds,
        )

    async def get_favorite_artists(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "isFavorite": "true", "enableUserData": "true", "limit": limit, "Fields": "ProviderIds"}
        return await self._fetch_items("/Artists", f"jellyfin_fav_artists:{uid}:{limit}", params, "Failed to get favorite artists")

    async def get_favorite_albums(
        self,
        user_id: str | None = None,
        limit: int = 20,
        ttl_seconds: int = 300,
    ) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "includeItemTypes": "MusicAlbum", "isFavorite": "true",
                  "enableUserData": "true", "limit": limit, "recursive": "true"}
        return await self._fetch_items(
            "/Items",
            f"jellyfin_fav_albums:{uid}:{limit}",
            params,
            "Failed to get favorite albums",
            ttl=ttl_seconds,
        )

    async def get_most_played_artists(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "sortBy": "PlayCount", "sortOrder": "Descending",
                  "enableUserData": "true", "limit": limit}
        filter_fn = lambda i: i.get("UserData", {}).get("PlayCount", 0) > 0
        return await self._fetch_items("/Artists", f"jellyfin_top_artists:{uid}:{limit}", params, "Failed to get most played artists", filter_fn=filter_fn)

    async def get_most_played_albums(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "includeItemTypes": "MusicAlbum", "sortBy": "PlayCount",
                  "sortOrder": "Descending", "enableUserData": "true", "limit": limit, "recursive": "true"}
        filter_fn = lambda i: i.get("UserData", {}).get("PlayCount", 0) > 0
        return await self._fetch_items("/Items", f"jellyfin_top_albums:{uid}:{limit}", params, "Failed to get most played albums", filter_fn=filter_fn)

    async def get_recently_added(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "includeItemTypes": "MusicAlbum", "limit": limit, "enableUserData": "true"}
        try:
            result = await self._get("/Items/Latest", params=params)
            return [parse_item(item) for item in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get recently added: {e}")
            return []

    async def get_genres(self, user_id: str | None = None, ttl_seconds: int = 3600) -> list[str]:
        uid = user_id or self._user_id
        cache_key = f"jellyfin_genres:{uid}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        params: dict[str, Any] = {"userId": uid} if uid else {}
        try:
            result = await self._get("/MusicGenres", params=params)
            if not result:
                return []
            genres = [item.get("Name", "") for item in result.get("Items", []) if item.get("Name")]
            await self._cache.set(cache_key, genres, ttl_seconds=ttl_seconds)
            return genres
        except Exception as e:
            logger.error(f"Failed to get genres: {e}")
            return []

    async def get_artists_by_genre(self, genre: str, user_id: str | None = None, limit: int = 50) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        params: dict[str, Any] = {"genres": genre, "limit": limit, "enableUserData": "true"}
        if uid:
            params["userId"] = uid
        try:
            result = await self._get("/Artists", params=params)
            return [parse_item(item) for item in result.get("Items", [])] if result else []
        except Exception as e:
            logger.error(f"Failed to get artists by genre: {e}")
            return []
    
    def get_auth_headers(self) -> dict[str, str]:
        return {"X-Emby-Token": self._api_key}

    def get_image_url(self, item_id: str, image_tag: str | None = None) -> str | None:
        if not self._base_url or not item_id:
            return None
        
        url = f"{self._base_url}/Items/{item_id}/Images/Primary"
        if image_tag:
            url += f"?tag={image_tag}"
        
        return url

    async def _post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("POST", endpoint, json_data=json_data)

    async def get_albums(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "SortName",
        sort_order: str = "Ascending",
        genre: str | None = None,
    ) -> tuple[list[JellyfinItem], int]:
        uid = self._user_id
        params: dict[str, Any] = {
            "includeItemTypes": "MusicAlbum",
            "recursive": "true",
            "sortBy": sort_by,
            "sortOrder": sort_order,
            "limit": limit,
            "startIndex": offset,
            "enableUserData": "true",
            "Fields": "ProviderIds,ChildCount",
        }
        if uid:
            params["userId"] = uid
        if genre:
            params["genres"] = genre
        cache_key = f"jellyfin_albums:{uid}:{limit}:{offset}:{sort_by}:{sort_order}:{genre}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        try:
            result = await self._get("/Items", params=params)
            if not result:
                return [], 0
            raw_items = result.get("Items", [])
            total = result.get("TotalRecordCount", len(raw_items))
            items = [parse_item(i) for i in raw_items]
            pair = (items, total)
            if items:
                await self._cache.set(cache_key, pair, ttl_seconds=120)
            return pair
        except Exception as e:
            logger.error("Failed to get albums: %s", e)
            return [], 0

    async def get_album_tracks(self, album_id: str) -> list[JellyfinItem]:
        uid = self._user_id
        params: dict[str, Any] = {
            "albumIds": album_id,
            "includeItemTypes": "Audio",
            "sortBy": "IndexNumber",
            "sortOrder": "Ascending",
            "recursive": "true",
            "enableUserData": "true",
            "Fields": "ProviderIds,MediaStreams",
        }
        if uid:
            params["userId"] = uid
        cache_key = f"jellyfin_album_tracks:{album_id}"
        return await self._fetch_items(
            "/Items",
            cache_key,
            params,
            f"Failed to get tracks for album {album_id}",
            ttl=120,
            raise_on_error=True,
        )

    async def get_album_detail(self, album_id: str) -> JellyfinItem | None:
        uid = self._user_id
        params: dict[str, Any] = {"Fields": "ProviderIds,ChildCount"}
        if uid:
            params["userId"] = uid
        try:
            result = await self._get(f"/Items/{album_id}", params=params)
            return parse_item(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get album detail {album_id}: {e}")
            return None

    async def get_album_by_mbid(self, musicbrainz_id: str) -> JellyfinItem | None:
        index = await self.build_mbid_index()
        jellyfin_id = index.get(musicbrainz_id)
        if jellyfin_id:
            return await self.get_album_detail(jellyfin_id)

        try:
            results = await self.search_items(musicbrainz_id, item_types="MusicAlbum")
            for item in results:
                if not item.provider_ids:
                    continue
                if (
                    item.provider_ids.get("MusicBrainzReleaseGroup") == musicbrainz_id
                    or item.provider_ids.get("MusicBrainzAlbum") == musicbrainz_id
                ):
                    return item
        except Exception as e:
            logger.debug(f"MBID search fallback failed for {musicbrainz_id}: {e}")

        return None

    async def get_artist_by_mbid(self, musicbrainz_id: str) -> JellyfinItem | None:
        try:
            results = await self.search_items(musicbrainz_id, item_types="MusicArtist")
            for item in results:
                if not item.provider_ids:
                    continue
                if item.provider_ids.get("MusicBrainzArtist") == musicbrainz_id:
                    return item
        except Exception as e:
            logger.debug(f"Artist MBID search fallback failed for {musicbrainz_id}: {e}")

        return None

    async def get_artists(
        self, limit: int = 50, offset: int = 0
    ) -> list[JellyfinItem]:
        params: dict[str, Any] = {
            "limit": limit,
            "startIndex": offset,
            "enableUserData": "true",
            "Fields": "ProviderIds",
        }
        if self._user_id:
            params["userId"] = self._user_id
        cache_key = f"jellyfin_artists:{self._user_id}:{limit}:{offset}"
        return await self._fetch_items(
            "/Artists", cache_key, params, "Failed to get artists", ttl=120
        )

    async def build_mbid_index(self) -> dict[str, str]:
        cache_key = f"jellyfin_mbid_index:{self._user_id or 'default'}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        if self._library_cache:
            sqlite_index = await self._library_cache.load_jellyfin_mbid_index(
                max_age_seconds=3600
            )
            if sqlite_index:
                await self._cache.set(cache_key, sqlite_index, ttl_seconds=3600)
                logger.info(
                    f"Loaded MBID index from SQLite with {len(sqlite_index)} entries"
                )
                return sqlite_index

        index: dict[str, str] = {}
        try:
            offset = 0
            batch_size = 500
            while True:
                params: dict[str, Any] = {
                    "includeItemTypes": "MusicAlbum",
                    "recursive": "true",
                    "Fields": "ProviderIds",
                    "limit": batch_size,
                    "startIndex": offset,
                }
                if self._user_id:
                    params["userId"] = self._user_id

                result = await self._get("/Items", params=params)
                if not result:
                    break

                items = result.get("Items", [])
                if not items:
                    break

                for item in items:
                    provider_ids = item.get("ProviderIds", {})
                    item_id = item.get("Id")
                    if not item_id:
                        continue
                    rg_mbid = provider_ids.get("MusicBrainzReleaseGroup")
                    if rg_mbid:
                        index[rg_mbid] = item_id
                    release_mbid = provider_ids.get("MusicBrainzAlbum")
                    if release_mbid:
                        index[release_mbid] = item_id

                total = result.get("TotalRecordCount", 0)
                offset += batch_size
                if offset >= total:
                    break

            if index:
                await self._cache.set(cache_key, index, ttl_seconds=3600)
                if self._library_cache:
                    await self._library_cache.save_jellyfin_mbid_index(index)
            logger.info(f"Built Jellyfin MBID index with {len(index)} entries")
        except Exception as e:
            logger.error(f"Failed to build MBID index: {e}")

        return index

    async def search_items(
        self,
        query: str,
        item_types: str = "MusicAlbum,Audio,MusicArtist",
    ) -> list[JellyfinItem]:
        params: dict[str, Any] = {
            "searchTerm": query,
            "includeItemTypes": item_types,
            "limit": 50,
            "Fields": "ProviderIds",
        }
        if self._user_id:
            params["userId"] = self._user_id
        try:
            result = await self._get("/Search/Hints", params=params)
            if not result:
                return []
            raw_items = result.get("SearchHints", [])
            return [parse_item(item) for item in raw_items]
        except Exception as e:
            logger.error(f"Jellyfin search failed for '{query}': {e}")
            return []

    async def get_library_stats(self, ttl_seconds: int = 600) -> dict[str, Any]:
        cache_key = "jellyfin_library_stats"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        stats: dict[str, Any] = {"total_albums": 0, "total_artists": 0, "total_tracks": 0}
        try:
            for item_type, key in [
                ("MusicAlbum", "total_albums"),
                ("MusicArtist", "total_artists"),
                ("Audio", "total_tracks"),
            ]:
                params: dict[str, Any] = {
                    "includeItemTypes": item_type,
                    "recursive": "true",
                    "limit": 0,
                }
                if self._user_id:
                    params["userId"] = self._user_id
                result = await self._get("/Items", params=params)
                if result:
                    stats[key] = result.get("TotalRecordCount", 0)

            await self._cache.set(cache_key, stats, ttl_seconds=ttl_seconds)
        except Exception as e:
            logger.error(f"Failed to get library stats: {e}")

        return stats

    def get_stream_url(
        self, item_id: str, audio_codec: str = "aac", bitrate: int = 128000
    ) -> str:
        container = audio_codec if audio_codec != "vorbis" else "ogg"
        parts = [
            f"{self._base_url}/Audio/{item_id}/universal",
            f"?container={container}",
            f"&audioCodec={audio_codec}",
            f"&audioBitRate={bitrate}",
            f"&maxAudioChannels=2",
            f"&transcodingContainer={container}",
            f"&transcodingProtocol=http",
        ]
        if self._user_id:
            parts.append(f"&userId={self._user_id}")
        return "".join(parts)

    async def get_playback_info(self, item_id: str) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self._user_id:
            params["userId"] = self._user_id
        result = await self._get(f"/Items/{item_id}/PlaybackInfo", params=params)
        if not result:
            raise ResourceNotFoundError(f"Playback info not found for {item_id}")
        return result

    async def report_playback_start(
        self, item_id: str, play_session_id: str
    ) -> None:
        body: dict[str, Any] = {
            "ItemId": item_id,
            "PlaySessionId": play_session_id,
            "CanSeek": True,
            "PlayMethod": "Transcode",
        }
        await self._post("/Sessions/Playing", json_data=body)

    async def report_playback_progress(
        self,
        item_id: str,
        play_session_id: str,
        position_ticks: int,
        is_paused: bool,
    ) -> None:
        body: dict[str, Any] = {
            "ItemId": item_id,
            "PlaySessionId": play_session_id,
            "PositionTicks": position_ticks,
            "IsPaused": is_paused,
            "CanSeek": True,
        }
        await self._post("/Sessions/Playing/Progress", json_data=body)

    async def report_playback_stopped(
        self, item_id: str, play_session_id: str, position_ticks: int
    ) -> None:
        body: dict[str, Any] = {
            "ItemId": item_id,
            "PlaySessionId": play_session_id,
            "PositionTicks": position_ticks,
        }
        await self._post("/Sessions/Playing/Stopped", json_data=body)

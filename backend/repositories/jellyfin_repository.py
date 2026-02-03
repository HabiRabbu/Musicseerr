import httpx
import logging
from typing import Any
from core.exceptions import ExternalServiceError
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from repositories.jellyfin_models import JellyfinItem, JellyfinUser, parse_item, parse_user

logger = logging.getLogger(__name__)

_jellyfin_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="jellyfin"
)


class JellyfinRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
        base_url: str = "",
        api_key: str = "",
        user_id: str = ""
    ):
        self._client = http_client
        self._cache = cache
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
                return response.json()
            except ValueError:
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
            
            result = response.json()
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
            
            result = response.json()
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
        filter_fn=None
    ) -> list[JellyfinItem]:
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        try:
            result = await self._get(endpoint, params=params)
            if not result:
                logger.warning(f"{error_msg}: _get returned None/empty")
                return []
            raw_items = result.get("Items", []) if isinstance(result, dict) else result
            items = [parse_item(i) for i in raw_items if not filter_fn or filter_fn(i)]
            if items:
                await self._cache.set(cache_key, items, ttl_seconds=ttl)
            return items
        except Exception as e:
            logger.error(f"{error_msg}: {e}")
            return []

    async def get_recently_played(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "includeItemTypes": "Audio", "sortBy": "DatePlayed",
                  "sortOrder": "Descending", "isPlayed": "true", "enableUserData": "true",
                  "limit": limit, "recursive": "true", "Fields": "ProviderIds"}
        return await self._fetch_items("/Items", f"jellyfin_recent:{uid}:{limit}", params, "Failed to get recently played")

    async def get_favorite_artists(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "isFavorite": "true", "enableUserData": "true", "limit": limit, "Fields": "ProviderIds"}
        return await self._fetch_items("/Artists", f"jellyfin_fav_artists:{uid}:{limit}", params, "Failed to get favorite artists")

    async def get_favorite_albums(self, user_id: str | None = None, limit: int = 20) -> list[JellyfinItem]:
        uid = user_id or self._user_id
        if not uid:
            return []
        params = {"userId": uid, "includeItemTypes": "MusicAlbum", "isFavorite": "true",
                  "enableUserData": "true", "limit": limit, "recursive": "true"}
        return await self._fetch_items("/Items", f"jellyfin_fav_albums:{uid}:{limit}", params, "Failed to get favorite albums")

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

    async def get_genres(self, user_id: str | None = None) -> list[str]:
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
            await self._cache.set(cache_key, genres, ttl_seconds=3600)
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
    
    def get_image_url(self, item_id: str, image_tag: str | None = None) -> str | None:
        if not self._base_url or not item_id:
            return None
        
        url = f"{self._base_url}/Items/{item_id}/Images/Primary"
        if image_tag:
            url += f"?tag={image_tag}"
        
        return url

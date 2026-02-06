import httpx
import logging
from typing import Any
from core.exceptions import ExternalServiceError
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.resilience.retry import with_retry, CircuitBreaker
from repositories.listenbrainz_models import (
    ListenBrainzArtist, ListenBrainzReleaseGroup, ListenBrainzRecording,
    ListenBrainzListen, ListenBrainzGenreActivity, ListenBrainzSimilarArtist,
    ALLOWED_STATS_RANGE,
    parse_artist, parse_release_group, parse_recording, parse_listen,
    parse_artist_recording, parse_similar_artist,
)

logger = logging.getLogger(__name__)

_listenbrainz_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="listenbrainz"
)

LISTENBRAINZ_API_URL = "https://api.listenbrainz.org"


class ListenBrainzRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
        username: str = "",
        user_token: str = ""
    ):
        self._client = http_client
        self._cache = cache
        self._username = username
        self._user_token = user_token
        self._base_url = LISTENBRAINZ_API_URL
    
    def configure(self, username: str, user_token: str = "") -> None:
        self._username = username
        self._user_token = user_token
    
    @staticmethod
    def reset_circuit_breaker() -> None:
        _listenbrainz_circuit_breaker.reset()
    
    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._user_token:
            headers["Authorization"] = f"Token {self._user_token}"
        return headers
    
    @with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        circuit_breaker=_listenbrainz_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError, ExternalServiceError)
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        require_auth: bool = False,
    ) -> Any:
        url = f"{self._base_url}{endpoint}"
        
        if require_auth and not self._user_token:
            raise ExternalServiceError("ListenBrainz user token required for this request")
        
        try:
            response = await self._client.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
                timeout=15.0,
            )
            
            if response.status_code == 204:
                return None
            
            if response.status_code == 404:
                return None
            
            if response.status_code != 200:
                raise ExternalServiceError(
                    f"ListenBrainz {method} failed ({response.status_code})",
                    response.text
                )
            
            try:
                return response.json()
            except ValueError:
                return None
        
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"ListenBrainz request failed: {str(e)}")
    
    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        require_auth: bool = False
    ) -> Any:
        return await self._request("GET", endpoint, params=params, require_auth=require_auth)
    
    async def _post(
        self,
        endpoint: str,
        data: dict[str, Any],
        require_auth: bool = False
    ) -> Any:
        return await self._request("POST", endpoint, json_data=data, require_auth=require_auth)
    
    async def validate_username(self, username: str | None = None) -> tuple[bool, str]:
        user = username or self._username
        if not user:
            return False, "No username provided"
        
        try:
            url = f"{self._base_url}/1/user/{user}/listen-count"
            response = await self._client.request(
                "GET",
                url,
                headers=self._get_headers(),
                timeout=10.0,
            )
            
            if response.status_code == 404:
                return False, f"User '{user}' not found"
            
            if response.status_code != 200:
                return False, f"Validation failed (HTTP {response.status_code})"
            
            result = response.json()
            if result and "payload" in result:
                count = result.get("payload", {}).get("count", 0)
                return True, f"User found with {count:,} listens"
            return False, "User not found"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except httpx.ConnectError:
            return False, "Could not connect to ListenBrainz"
        except Exception as e:
            return False, f"Validation failed: {str(e)}"
    
    async def validate_token(self) -> tuple[bool, str]:
        if not self._user_token:
            return False, "No token provided"
        
        try:
            url = f"{self._base_url}/1/validate-token"
            headers = self._get_headers()
            response = await self._client.request(
                "GET",
                url,
                headers=headers,
                timeout=10.0,
            )
            
            if response.status_code != 200:
                return False, "Token invalid or expired"
            
            result = response.json()
            if result and result.get("valid"):
                username = result.get("user_name", self._username)
                return True, f"Successfully connected as '{username}'"
            return False, "Token invalid"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except httpx.ConnectError:
            return False, "Could not connect to ListenBrainz"
        except Exception as e:
            return False, f"Validation failed: {str(e)}"
    
    async def get_user_listens(
        self,
        username: str | None = None,
        count: int = 25,
        max_ts: int | None = None,
        min_ts: int | None = None
    ) -> list[ListenBrainzListen]:
        user = username or self._username
        if not user:
            return []
        
        params: dict[str, Any] = {"count": min(count, 100)}
        if max_ts:
            params["max_ts"] = max_ts
        if min_ts:
            params["min_ts"] = min_ts
        
        result = await self._get(f"/1/user/{user}/listens", params=params)
        if not result:
            return []
        return [parse_listen(item) for item in result.get("payload", {}).get("listens", [])]
    
    async def get_user_top_artists(
        self,
        username: str | None = None,
        range_: str = "this_month",
        count: int = 25,
        offset: int = 0
    ) -> list[ListenBrainzArtist]:
        user = username or self._username
        if not user:
            return []
        
        if range_ not in ALLOWED_STATS_RANGE:
            range_ = "this_month"
        
        cache_key = f"lb_user_artists:{user}:{range_}:{count}:{offset}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        params = {"count": min(count, 100), "offset": offset, "range": range_}
        result = await self._get(f"/1/stats/user/{user}/artists", params=params)
        if not result:
            return []
        artists = [parse_artist(item) for item in result.get("payload", {}).get("artists", [])]
        if artists:
            await self._cache.set(cache_key, artists, ttl_seconds=300)
        return artists
    
    async def get_user_top_release_groups(
        self,
        username: str | None = None,
        range_: str = "this_month",
        count: int = 25,
        offset: int = 0
    ) -> list[ListenBrainzReleaseGroup]:
        user = username or self._username
        if not user:
            return []
        
        if range_ not in ALLOWED_STATS_RANGE:
            range_ = "this_month"
        
        cache_key = f"lb_user_release_groups:{user}:{range_}:{count}:{offset}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        params = {"count": min(count, 100), "offset": offset, "range": range_}
        result = await self._get(f"/1/stats/user/{user}/release-groups", params=params)
        if not result:
            return []
        groups = [parse_release_group(item) for item in result.get("payload", {}).get("release_groups", [])]
        if groups:
            await self._cache.set(cache_key, groups, ttl_seconds=300)
        return groups
    
    async def get_user_top_recordings(
        self,
        username: str | None = None,
        range_: str = "this_month",
        count: int = 25,
        offset: int = 0
    ) -> list[ListenBrainzRecording]:
        user = username or self._username
        if not user:
            return []
        
        if range_ not in ALLOWED_STATS_RANGE:
            range_ = "this_month"
        
        params = {"count": min(count, 100), "offset": offset, "range": range_}
        result = await self._get(f"/1/stats/user/{user}/recordings", params=params)
        if not result:
            return []
        return [parse_recording(item) for item in result.get("payload", {}).get("recordings", [])]
    
    async def get_user_genre_activity(
        self,
        username: str | None = None
    ) -> list[ListenBrainzGenreActivity]:
        user = username or self._username
        if not user:
            return []
        
        cache_key = f"lb_user_genres:{user}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        result = await self._get(f"/1/stats/user/{user}/genre-activity")
        
        if not result:
            return []
        
        genre_counts: dict[str, int] = {}
        for item in result.get("result", []):
            genre = item.get("genre", "Unknown")
            count = item.get("listen_count", 0)
            genre_counts[genre] = genre_counts.get(genre, 0) + count
        
        genres = [
            ListenBrainzGenreActivity(genre=g, listen_count=c)
            for g, c in sorted(genre_counts.items(), key=lambda x: -x[1])
        ]
        
        if genres:
            await self._cache.set(cache_key, genres, ttl_seconds=300)
        return genres
    
    async def get_sitewide_top_artists(
        self,
        range_: str = "week",
        count: int = 25,
        offset: int = 0
    ) -> list[ListenBrainzArtist]:
        if range_ not in ALLOWED_STATS_RANGE:
            range_ = "week"
        
        cache_key = f"lb_sitewide_artists:{range_}:{count}:{offset}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        params = {"count": min(count, 100), "offset": offset, "range": range_}
        result = await self._get("/1/stats/sitewide/artists", params=params)
        if not result:
            return []
        artists = [parse_artist(item) for item in result.get("payload", {}).get("artists", [])]
        if artists:
            await self._cache.set(cache_key, artists, ttl_seconds=3600)
        return artists
    
    async def get_sitewide_top_release_groups(
        self,
        range_: str = "week",
        count: int = 25,
        offset: int = 0
    ) -> list[ListenBrainzReleaseGroup]:
        if range_ not in ALLOWED_STATS_RANGE:
            range_ = "week"
        
        cache_key = f"lb_sitewide_release_groups:{range_}:{count}:{offset}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        params = {"count": min(count, 100), "offset": offset, "range": range_}
        result = await self._get("/1/stats/sitewide/release-groups", params=params)
        if not result:
            return []
        groups = [parse_release_group(item) for item in result.get("payload", {}).get("release_groups", [])]
        if groups:
            await self._cache.set(cache_key, groups, ttl_seconds=3600)
        return groups
    
    async def get_sitewide_top_recordings(
        self,
        range_: str = "week",
        count: int = 25,
        offset: int = 0
    ) -> list[ListenBrainzRecording]:
        if range_ not in ALLOWED_STATS_RANGE:
            range_ = "week"
        
        cache_key = f"lb_sitewide_recordings:{range_}:{count}:{offset}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        params = {"count": min(count, 100), "offset": offset, "range": range_}
        result = await self._get("/1/stats/sitewide/recordings", params=params)
        if not result:
            return []
        recordings = [parse_recording(item) for item in result.get("payload", {}).get("recordings", [])]
        if recordings:
            await self._cache.set(cache_key, recordings, ttl_seconds=3600)
        return recordings
    
    async def get_artist_top_recordings(
        self,
        artist_mbid: str,
        count: int = 10
    ) -> list[ListenBrainzRecording]:
        cache_key = f"lb_artist_recordings:{artist_mbid}:{count}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        result = await self._get(f"/1/popularity/top-recordings-for-artist/{artist_mbid}")
        if not result:
            return []
        recordings = [parse_artist_recording(item) for item in result[:count]]
        if recordings:
            await self._cache.set(cache_key, recordings, ttl_seconds=3600)
        return recordings
    
    async def get_similar_users(
        self,
        username: str | None = None
    ) -> list[dict[str, Any]]:
        user = username or self._username
        if not user:
            return []
        
        result = await self._get(f"/1/user/{user}/similar-users")
        
        if not result:
            return []
        
        return result.get("payload", [])
    
    async def get_user_fresh_releases(
        self,
        username: str | None = None,
        past: bool = True,
        future: bool = False
    ) -> list[dict[str, Any]]:
        user = username or self._username
        if not user:
            return []
        
        cache_key = f"lb_fresh_releases:{user}:{past}:{future}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        
        params = {"past": str(past).lower(), "future": str(future).lower()}
        result = await self._get(f"/1/user/{user}/fresh_releases", params=params)
        
        if not result:
            return []
        
        releases = result.get("payload", {}).get("releases", [])
        if releases:
            await self._cache.set(cache_key, releases, ttl_seconds=3600)
        return releases

    async def get_similar_artists(
        self,
        artist_mbid: str,
        max_similar: int = 15,
        mode: str = "easy"
    ) -> list[ListenBrainzSimilarArtist]:
        cache_key = f"lb_similar_artists:{artist_mbid}:{max_similar}:{mode}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        params = {
            "mode": mode,
            "max_similar_artists": max_similar,
            "max_recordings_per_artist": 5,
            "pop_begin": 0,
            "pop_end": 100,
        }
        result = await self._get(f"/1/lb-radio/artist/{artist_mbid}", params=params)
        if not result or "error" in result:
            return []

        similar_artists: list[ListenBrainzSimilarArtist] = []
        for mbid, recordings in result.items():
            if mbid == artist_mbid:
                continue
            if not isinstance(recordings, list):
                continue
            similar_artists.append(parse_similar_artist(mbid, recordings))

        similar_artists.sort(key=lambda a: a.listen_count, reverse=True)
        if similar_artists:
            await self._cache.set(cache_key, similar_artists, ttl_seconds=3600)
        return similar_artists

    async def get_artist_top_release_groups(
        self,
        artist_mbid: str,
        count: int = 10
    ) -> list[ListenBrainzReleaseGroup]:
        cache_key = f"lb_artist_release_groups:{artist_mbid}:{count}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        result = await self._get(f"/1/popularity/top-release-groups-for-artist/{artist_mbid}")
        if not result or not isinstance(result, list):
            return []

        release_groups = []
        for item in result[:count]:
            rg = item.get("release_group", {})
            release_groups.append(ListenBrainzReleaseGroup(
                release_group_name=rg.get("name", "Unknown"),
                artist_name=item.get("artist", {}).get("name", "Unknown"),
                listen_count=item.get("total_listen_count", 0),
                release_group_mbid=item.get("release_group_mbid"),
                caa_release_mbid=rg.get("caa_release_mbid"),
                caa_id=rg.get("caa_id"),
            ))

        if release_groups:
            await self._cache.set(cache_key, release_groups, ttl_seconds=3600)
        return release_groups

    async def get_release_group_popularity_batch(
        self,
        release_group_mbids: list[str]
    ) -> dict[str, int]:
        """Get listen counts for multiple release groups in a single call.
        
        Returns a dict mapping mbid -> total_listen_count.
        """
        if not release_group_mbids:
            return {}

        result = await self._post(
            "/1/popularity/release-group",
            {"release_group_mbids": release_group_mbids}
        )
        if not result or not isinstance(result, list):
            return {}

        counts: dict[str, int] = {}
        for item in result:
            mbid = item.get("release_group_mbid")
            count = item.get("total_listen_count")
            if mbid and count is not None:
                counts[mbid] = count
        return counts

    def is_configured(self) -> bool:
        return bool(self._username)

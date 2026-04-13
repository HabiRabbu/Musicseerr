import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import OrderedDict

import httpx
import msgspec
from models.youtube import YouTubeQuotaResponse

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DEFAULT_DAILY_QUOTA_LIMIT = 80
SEARCH_COST = 100
PREVIEW_CACHE_MAX = 100

def get_quota_file_path() -> Path:
    from core.config import get_settings
    return get_settings().cache_dir / "youtube_quota.json"

class YouTubeQuotaState(msgspec.Struct):
    date: str = ""
    count: int = 0


class _YouTubeSearchId(msgspec.Struct):
    videoId: str | None = None


class _YouTubeSearchItem(msgspec.Struct):
    id: _YouTubeSearchId | None = None


class _YouTubeSearchResponse(msgspec.Struct):
    items: list[_YouTubeSearchItem] = []


def _decode_json_response(response: httpx.Response, decode_type: type[_YouTubeSearchResponse]) -> _YouTubeSearchResponse:
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray, memoryview)):
        return msgspec.json.decode(content, type=decode_type)
    return msgspec.convert(response.json(), type=decode_type)


class YouTubeRepository:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str = "",
        daily_quota_limit: int = DEFAULT_DAILY_QUOTA_LIMIT,
    ):
        self._http_client = http_client
        self._api_key = api_key
        self._daily_quota_limit = daily_quota_limit
        self._cache: OrderedDict[str, str | None] = OrderedDict()
        self._daily_count = 0
        self._quota_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._load_quota()

    def _load_quota(self) -> None:
        quota_file = get_quota_file_path()
        try:
            if quota_file.exists():
                data = msgspec.json.decode(quota_file.read_bytes(), type=YouTubeQuotaState)
                saved_date = data.date
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if saved_date == today:
                    self._daily_count = data.count
                    self._quota_date = saved_date
                else:
                    self._daily_count = 0
                    self._quota_date = today
                    self._save_quota()
        except Exception:  # noqa: BLE001
            pass

    def _save_quota(self) -> None:
        quota_file = get_quota_file_path()
        try:
            quota_file.parent.mkdir(parents=True, exist_ok=True)
            quota_file.write_bytes(msgspec.json.encode(YouTubeQuotaState(date=self._quota_date, count=self._daily_count)))
        except Exception:  # noqa: BLE001
            pass

    def configure(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _check_and_reset_quota(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._quota_date:
            self._daily_count = 0
            self._quota_date = today
            self._save_quota()

    @property
    def quota_remaining(self) -> int:
        self._check_and_reset_quota()
        return max(0, self._daily_quota_limit - self._daily_count)

    def get_quota_status(self) -> YouTubeQuotaResponse:
        self._check_and_reset_quota()
        return YouTubeQuotaResponse(
            used=self._daily_count,
            limit=self._daily_quota_limit,
            remaining=max(0, self._daily_quota_limit - self._daily_count),
            date=self._quota_date,
        )

    def _cache_put(self, key: str, value: str | None) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= PREVIEW_CACHE_MAX:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def is_cached(self, artist: str, album: str) -> bool:
        cache_key = f"{artist.lower()}|{album.lower()}"
        return cache_key in self._cache

    def are_cached(self, pairs: list[tuple[str, str]]) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for artist, track in pairs:
            cache_key = f"{artist.lower()}|{track.lower()}"
            result[cache_key] = cache_key in self._cache
        return result

    async def search_video(self, artist: str, album: str) -> str | None:
        if not self._api_key:
            return None

        cache_key = f"{artist.lower()}|{album.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._check_and_reset_quota()
        if self._daily_count >= self._daily_quota_limit:
            logger.warning("YouTube API daily quota exceeded")
            return None

        query = f"{artist} {album} full album"

        try:
            response = await self._http_client.get(
                YOUTUBE_SEARCH_URL,
                params={
                    "part": "id",
                    "type": "video",
                    "maxResults": 1,
                    "q": query,
                    "key": self._api_key,
                },
                timeout=10.0,
            )
            self._daily_count += 1
            self._save_quota()

            if response.status_code == 403:
                logger.error("YouTube API key invalid or quota exceeded upstream")
                return None

            response.raise_for_status()
            data = _decode_json_response(response, _YouTubeSearchResponse)

            if data.items:
                video_id = data.items[0].id.videoId if data.items[0].id else None
                self._cache_put(cache_key, video_id)
                return video_id

            self._cache_put(cache_key, None)
            return None
        except Exception as e:  # noqa: BLE001
            logger.error(f"YouTube search failed for '{query}': {e}")
            return None

    async def search_track(self, artist: str, track_name: str) -> str | None:
        if not self._api_key:
            return None

        cache_key = f"{artist.lower()}|{track_name.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._check_and_reset_quota()
        if self._daily_count >= self._daily_quota_limit:
            logger.warning("YouTube API daily quota exceeded")
            return None

        query = f"{artist} {track_name}"

        try:
            response = await self._http_client.get(
                YOUTUBE_SEARCH_URL,
                params={
                    "part": "id",
                    "type": "video",
                    "maxResults": 1,
                    "q": query,
                    "key": self._api_key,
                },
                timeout=10.0,
            )
            self._daily_count += 1
            self._save_quota()

            if response.status_code == 403:
                logger.error("YouTube API key invalid or quota exceeded upstream")
                return None

            response.raise_for_status()
            data = _decode_json_response(response, _YouTubeSearchResponse)

            if data.items:
                video_id = data.items[0].id.videoId if data.items[0].id else None
                self._cache_put(cache_key, video_id)
                return video_id

            self._cache_put(cache_key, None)
            return None
        except Exception as e:  # noqa: BLE001
            logger.error(f"YouTube track search failed for '{query}': {e}")
            return None

    async def verify_api_key(self, api_key: str) -> tuple[bool, str]:
        try:
            response = await self._http_client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "id",
                    "id": "dQw4w9WgXcQ",
                    "key": api_key,
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                return True, "YouTube API key is valid"
            elif response.status_code == 403:
                return False, "API key is invalid or YouTube Data API is not enabled"
            else:
                return False, f"Unexpected response: {response.status_code}"
        except Exception as e:  # noqa: BLE001
            return False, f"Connection error: {e}"

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DAILY_QUOTA_LIMIT = 80
SEARCH_COST = 100


class YouTubeRepository:
    def __init__(self, http_client: httpx.AsyncClient, api_key: str = ""):
        self._http_client = http_client
        self._api_key = api_key
        self._daily_count = 0
        self._quota_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._cache: dict[str, str | None] = {}

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

    @property
    def quota_remaining(self) -> int:
        self._check_and_reset_quota()
        return max(0, DAILY_QUOTA_LIMIT - self._daily_count)

    async def search_video(self, artist: str, album: str) -> str | None:
        if not self._api_key:
            return None

        self._check_and_reset_quota()
        if self._daily_count >= DAILY_QUOTA_LIMIT:
            logger.warning("YouTube API daily quota exceeded")
            return None

        cache_key = f"{artist.lower()}|{album.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

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

            if response.status_code == 403:
                logger.error("YouTube API key invalid or quota exceeded upstream")
                return None

            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if items:
                video_id = items[0].get("id", {}).get("videoId")
                self._cache[cache_key] = video_id
                return video_id

            self._cache[cache_key] = None
            return None
        except Exception as e:
            logger.error(f"YouTube search failed for '{query}': {e}")
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
        except Exception as e:
            return False, f"Connection error: {e}"

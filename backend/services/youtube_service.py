import logging
from datetime import datetime, timezone

from api.v1.schemas.youtube import YouTubeLink
from core.exceptions import ConfigurationError, ExternalServiceError, ResourceNotFoundError
from infrastructure.cache.persistent_cache import LibraryCache
from repositories.youtube import YouTubeRepository

logger = logging.getLogger(__name__)


class YouTubeService:

    def __init__(
        self,
        youtube_repo: YouTubeRepository,
        library_cache: LibraryCache,
    ):
        self._youtube_repo = youtube_repo
        self._library_cache = library_cache

    async def generate_link(
        self,
        artist_name: str,
        album_name: str,
        album_id: str,
        cover_url: str | None = None,
    ) -> YouTubeLink:
        if not self._youtube_repo.is_configured:
            raise ConfigurationError("YouTube API is not configured")

        existing = await self._library_cache.get_youtube_link(album_id)
        if existing:
            return YouTubeLink(**existing)

        if self._youtube_repo.quota_remaining <= 0:
            raise ExternalServiceError("YouTube daily quota exceeded")

        video_id = await self._youtube_repo.search_video(artist_name, album_name)
        if not video_id:
            raise ResourceNotFoundError(
                f"No YouTube video found for '{artist_name} - {album_name}'"
            )

        now = datetime.now(timezone.utc).isoformat()
        embed_url = f"https://www.youtube.com/embed/{video_id}"

        await self._library_cache.save_youtube_link(
            album_id=album_id,
            video_id=video_id,
            album_name=album_name,
            artist_name=artist_name,
            embed_url=embed_url,
            cover_url=cover_url,
            created_at=now,
        )

        return YouTubeLink(
            album_id=album_id,
            video_id=video_id,
            album_name=album_name,
            artist_name=artist_name,
            embed_url=embed_url,
            cover_url=cover_url,
            created_at=now,
        )

    async def get_link(self, album_id: str) -> YouTubeLink | None:
        result = await self._library_cache.get_youtube_link(album_id)
        return YouTubeLink(**result) if result else None

    async def get_all_links(self) -> list[YouTubeLink]:
        results = await self._library_cache.get_all_youtube_links()
        return [YouTubeLink(**row) for row in results]

    async def delete_link(self, album_id: str) -> None:
        await self._library_cache.delete_youtube_link(album_id)

    def get_quota_status(self) -> dict:
        return self._youtube_repo.get_quota_status()

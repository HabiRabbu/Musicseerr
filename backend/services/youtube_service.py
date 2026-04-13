import re
import uuid
from datetime import datetime, timezone

import msgspec

from api.v1.schemas.discover import YouTubeQuotaResponse
from api.v1.schemas.youtube import YouTubeLink, YouTubeTrackLink, YouTubeTrackLinkFailure
from core.exceptions import ConfigurationError, ExternalServiceError, ResourceNotFoundError, ValidationError
from infrastructure.persistence import YouTubeStore
from infrastructure.serialization import to_jsonable
from repositories.protocols import YouTubeRepositoryProtocol

_VIDEO_ID_RE = re.compile(
    r'(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
)
_RAW_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')


def extract_video_id(url: str) -> str | None:
    match = _VIDEO_ID_RE.search(url)
    if match:
        return match.group(1)
    if _RAW_ID_RE.match(url):
        return url
    return None


class YouTubeService:

    def __init__(
        self,
        youtube_repo: YouTubeRepositoryProtocol,
        youtube_store: YouTubeStore,
    ):
        self._youtube_repo = youtube_repo
        self._youtube_store = youtube_store

    async def generate_link(
        self,
        artist_name: str,
        album_name: str,
        album_id: str,
        cover_url: str | None = None,
    ) -> YouTubeLink:
        if not self._youtube_repo.is_configured:
            raise ConfigurationError("YouTube API is not configured")

        existing = await self._youtube_store.get_youtube_link(album_id)
        if existing and existing.get("video_id"):
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

        await self._youtube_store.save_youtube_link(
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
        result = await self._youtube_store.get_youtube_link(album_id)
        return YouTubeLink(**result) if result else None

    async def get_all_links(self) -> list[YouTubeLink]:
        results = await self._youtube_store.get_all_youtube_links()
        return [YouTubeLink(**row) for row in results]

    async def delete_link(self, album_id: str) -> None:
        await self._youtube_store.delete_youtube_link(album_id)

    def get_quota_status(self) -> YouTubeQuotaResponse:
        return self._youtube_repo.get_quota_status()

    async def generate_track_link(
        self,
        album_id: str,
        album_name: str,
        artist_name: str,
        track_name: str,
        track_number: int,
        disc_number: int = 1,
        cover_url: str | None = None,
    ) -> YouTubeTrackLink:
        if not self._youtube_repo.is_configured:
            raise ConfigurationError("YouTube API is not configured")

        if self._youtube_repo.quota_remaining <= 0:
            raise ExternalServiceError("YouTube daily quota exceeded")

        video_id = await self._youtube_repo.search_track(artist_name, track_name)
        if not video_id:
            raise ResourceNotFoundError(
                f"No YouTube video found for '{track_name} - {artist_name}'"
            )

        now = datetime.now(timezone.utc).isoformat()
        embed_url = f"https://www.youtube.com/embed/{video_id}"

        await self._youtube_store.save_youtube_track_link(
            album_id=album_id,
            album_name=album_name,
            track_number=track_number,
            disc_number=disc_number,
            track_name=track_name,
            video_id=video_id,
            artist_name=artist_name,
            embed_url=embed_url,
            created_at=now,
        )

        await self._youtube_store.ensure_youtube_album_entry(
            album_id=album_id,
            album_name=album_name,
            artist_name=artist_name,
            cover_url=cover_url,
            created_at=now,
        )

        return YouTubeTrackLink(
            album_id=album_id,
            track_number=track_number,
            disc_number=disc_number,
            track_name=track_name,
            video_id=video_id,
            artist_name=artist_name,
            embed_url=embed_url,
            created_at=now,
        )

    async def generate_track_links_batch(
        self,
        album_id: str,
        album_name: str,
        artist_name: str,
        tracks: list[dict],
        cover_url: str | None = None,
    ) -> tuple[list[YouTubeTrackLink], list[YouTubeTrackLinkFailure]]:
        if not self._youtube_repo.is_configured:
            raise ConfigurationError("YouTube API is not configured")

        generated: list[YouTubeTrackLink] = []
        failed: list[YouTubeTrackLinkFailure] = []
        batch_to_save: list[dict] = []

        for track in tracks:
            if self._youtube_repo.quota_remaining <= 0:
                failed.append(
                        YouTubeTrackLinkFailure(
                            track_number=track["track_number"],
                            disc_number=track.get("disc_number", 1),
                            track_name=track["track_name"],
                            reason="Quota exceeded",
                        )
                )
                continue

            try:
                video_id = await self._youtube_repo.search_track(artist_name, track["track_name"])
                if not video_id:
                    failed.append(
                        YouTubeTrackLinkFailure(
                            track_number=track["track_number"],
                            disc_number=track.get("disc_number", 1),
                            track_name=track["track_name"],
                            reason="No video found",
                        )
                    )
                    continue

                now = datetime.now(timezone.utc).isoformat()
                embed_url = f"https://www.youtube.com/embed/{video_id}"

                link = YouTubeTrackLink(
                    album_id=album_id,
                    track_number=track["track_number"],
                    disc_number=track.get("disc_number", 1),
                    track_name=track["track_name"],
                    video_id=video_id,
                    artist_name=artist_name,
                    embed_url=embed_url,
                    created_at=now,
                )
                generated.append(link)
                batch_to_save.append({**to_jsonable(link), "album_name": album_name})
            except Exception as e:  # noqa: BLE001
                failed.append(
                    YouTubeTrackLinkFailure(
                        track_number=track["track_number"],
                        disc_number=track.get("disc_number", 1),
                        track_name=track["track_name"],
                        reason=str(e),
                    )
                )

        if batch_to_save:
            await self._youtube_store.save_youtube_track_links_batch(album_id, batch_to_save)

        if generated:
            await self._youtube_store.ensure_youtube_album_entry(
                album_id=album_id,
                album_name=album_name,
                artist_name=artist_name,
                cover_url=cover_url,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        return generated, failed

    async def get_track_links(self, album_id: str) -> list[YouTubeTrackLink]:
        results = await self._youtube_store.get_youtube_track_links(album_id)
        return [YouTubeTrackLink(**row) for row in results]

    async def delete_track_link(self, album_id: str, disc_number: int, track_number: int) -> None:
        await self._youtube_store.delete_youtube_track_link(album_id, disc_number, track_number)
        await self._youtube_store.update_youtube_link_track_count(album_id)

    async def _save_and_return_link(self, **kwargs: object) -> YouTubeLink:
        await self._youtube_store.save_youtube_link(**kwargs)
        return YouTubeLink(**kwargs)

    async def save_manual_link(
        self,
        album_name: str,
        artist_name: str,
        youtube_url: str,
        cover_url: str | None = None,
        album_id: str | None = None,
    ) -> YouTubeLink:
        video_id = extract_video_id(youtube_url)
        if not video_id:
            raise ValidationError("Invalid YouTube URL: could not extract a video ID")

        if not album_id:
            album_id = f"manual-{uuid.uuid4().hex[:12]}"

        return await self._save_and_return_link(
            album_id=album_id,
            video_id=video_id,
            album_name=album_name,
            artist_name=artist_name,
            embed_url=f"https://www.youtube.com/embed/{video_id}",
            cover_url=cover_url,
            created_at=datetime.now(timezone.utc).isoformat(),
            is_manual=True,
        )

    async def update_link(
        self,
        album_id: str,
        youtube_url: str | None = None,
        album_name: str | None = None,
        artist_name: str | None = None,
        cover_url: str | None | msgspec.UnsetType = msgspec.UNSET,
    ) -> YouTubeLink:
        existing = await self._youtube_store.get_youtube_link(album_id)
        if not existing:
            raise ResourceNotFoundError(f"No YouTube link found for album '{album_id}'")

        video_id = existing["video_id"]
        embed_url = existing["embed_url"]
        if youtube_url:
            new_vid = extract_video_id(youtube_url)
            if not new_vid:
                raise ValidationError("Invalid YouTube URL: could not extract a video ID")
            video_id = new_vid
            embed_url = f"https://www.youtube.com/embed/{new_vid}"

        final_album_name = album_name or existing["album_name"]
        final_artist_name = artist_name or existing["artist_name"]
        final_cover_url = existing.get("cover_url") if cover_url is msgspec.UNSET else cover_url

        return await self._save_and_return_link(
            album_id=album_id,
            video_id=video_id,
            album_name=final_album_name,
            artist_name=final_artist_name,
            embed_url=embed_url,
            cover_url=final_cover_url,
            created_at=existing["created_at"],
            is_manual=bool(existing.get("is_manual", 0)),
        )

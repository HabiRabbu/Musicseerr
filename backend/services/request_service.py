import logging
from repositories.protocols import LidarrRepositoryProtocol
from infrastructure.queue.request_queue import RequestQueue
from infrastructure.persistence.request_history import RequestHistoryStore
from api.v1.schemas.request import QueueStatusResponse, RequestAcceptedResponse
from core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class RequestService:
    def __init__(
        self,
        lidarr_repo: LidarrRepositoryProtocol,
        request_queue: RequestQueue,
        request_history: RequestHistoryStore,
    ):
        self._lidarr_repo = lidarr_repo
        self._request_queue = request_queue
        self._request_history = request_history
    
    async def request_album(
        self,
        musicbrainz_id: str,
        artist: str | None = None,
        album: str | None = None,
        year: int | None = None,
        artist_mbid: str | None = None,
        monitor_artist: bool = False,
        auto_download_artist: bool = False,
    ) -> RequestAcceptedResponse:
        if not self._lidarr_repo.is_configured():
            raise ExternalServiceError("Lidarr isn't configured. Add an API key in Settings before requesting albums.")

        try:
            # Don't overwrite an active record (pending/downloading) — just re-check the queue.
            existing = await self._request_history.async_get_record(musicbrainz_id)
            if existing and existing.status in ("pending", "downloading"):
                # Merge monitoring flags if the user updated their choice on re-request
                if monitor_artist and not existing.monitor_artist:
                    await self._request_history.async_update_monitoring_flags(
                        musicbrainz_id, monitor_artist=True, auto_download_artist=auto_download_artist,
                    )
                enqueued = await self._request_queue.enqueue(musicbrainz_id)
                return RequestAcceptedResponse(
                    success=True,
                    message="Request already in progress",
                    musicbrainz_id=musicbrainz_id,
                    status=existing.status,
                )
            await self._request_history.async_record_request(
                musicbrainz_id=musicbrainz_id,
                artist_name=artist or "Unknown",
                album_title=album or "Unknown",
                year=year,
                artist_mbid=artist_mbid,
                monitor_artist=monitor_artist,
                auto_download_artist=auto_download_artist,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to record request history for %s: %s", musicbrainz_id, e)
            raise ExternalServiceError(f"Failed to record request: {e}")

        try:
            enqueued = await self._request_queue.enqueue(musicbrainz_id)
            if not enqueued:
                return RequestAcceptedResponse(
                    success=True,
                    message="Request already in queue",
                    musicbrainz_id=musicbrainz_id,
                    status="pending",
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to enqueue album %s: %s", musicbrainz_id, e)
            try:
                from datetime import datetime, timezone
                await self._request_history.async_update_status(
                    musicbrainz_id, "failed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception:  # noqa: BLE001
                pass
            raise ExternalServiceError(f"Failed to enqueue request: {e}")

        return RequestAcceptedResponse(
            success=True,
            message="Request accepted",
            musicbrainz_id=musicbrainz_id,
            status="pending",
        )
    
    def get_queue_status(self) -> QueueStatusResponse:
        status = self._request_queue.get_status()
        return QueueStatusResponse(
            queue_size=status["queue_size"],
            processing=status["processing"],
            active_workers=status.get("active_workers", 0),
            max_workers=status.get("max_workers", 1),
        )

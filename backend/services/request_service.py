import logging
from repositories.protocols import LidarrRepositoryProtocol
from infrastructure.queue.request_queue import RequestQueue
from infrastructure.cache.request_history import RequestHistoryStore
from api.v1.schemas.request import QueueStatusResponse
from core.exceptions import ExternalServiceError
from services.request_utils import extract_cover_url

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
    
    async def request_album(self, musicbrainz_id: str, artist: str | None = None, album: str | None = None, year: int | None = None) -> dict:
        try:
            result = await self._request_queue.add(musicbrainz_id)

            payload = result.get("payload", {})
            lidarr_album_id = None
            cover_url = None
            artist_mbid = None
            resolved_artist = artist or "Unknown"
            resolved_album = album or "Unknown"

            if payload and isinstance(payload, dict):
                lidarr_album_id = payload.get("id")
                resolved_album = payload.get("title") or resolved_album
                cover_url = extract_cover_url(payload)

                artist_data = payload.get("artist", {})
                if artist_data:
                    resolved_artist = artist_data.get("artistName") or resolved_artist
                    artist_mbid = artist_data.get("foreignArtistId")

            try:
                await self._request_history.async_record_request(
                    musicbrainz_id=musicbrainz_id,
                    artist_name=resolved_artist,
                    album_title=resolved_album,
                    year=year,
                    cover_url=cover_url,
                    artist_mbid=artist_mbid,
                    lidarr_album_id=lidarr_album_id,
                )
            except Exception as e:
                logger.error("Failed to persist request history for %s: %s", musicbrainz_id, e)

            return {
                "success": True,
                "message": result["message"],
                "lidarr_response": payload,
            }
        except Exception as e:
            logger.error("Failed to request album %s: %s", musicbrainz_id, e)
            raise ExternalServiceError(f"Failed to request album: {e}")
    
    def get_queue_status(self) -> QueueStatusResponse:
        status = self._request_queue.get_status()
        return QueueStatusResponse(
            queue_size=status["queue_size"],
            processing=status["processing"]
        )

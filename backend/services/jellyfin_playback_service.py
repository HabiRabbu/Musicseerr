import logging

import httpx
from fastapi.responses import Response, StreamingResponse

from core.exceptions import ExternalServiceError, PlaybackNotAllowedError
from infrastructure.constants import JELLYFIN_TICKS_PER_SECOND
from repositories.navidrome_models import StreamProxyResult
from repositories.protocols import JellyfinRepositoryProtocol

logger = logging.getLogger(__name__)


class JellyfinPlaybackService:
    def __init__(self, jellyfin_repo: JellyfinRepositoryProtocol):
        self._jellyfin = jellyfin_repo

    async def start_playback(self, item_id: str, play_session_id: str | None = None) -> str:
        """Report playback start to Jellyfin. Returns play_session_id.

        Handles nullable PlaySessionId and checks for ErrorCode in the
        PlaybackInfoResponse (NotAllowed, NoCompatibleStream, RateLimitExceeded).
        """
        resolved_play_session_id = play_session_id
        play_method = "DirectPlay"

        if not resolved_play_session_id:
            info = await self._jellyfin.get_playback_info(item_id)

            error_code = info.get("ErrorCode")
            if error_code:
                raise PlaybackNotAllowedError(
                    f"Jellyfin playback not allowed: {error_code}"
                )

            resolved_play_session_id = info.get("PlaySessionId")
            if not resolved_play_session_id:
                logger.warning(
                    "Jellyfin returned null PlaySessionId for item %s — "
                    "streaming without session reporting",
                    item_id,
                )
                return ""

            media_sources = info.get("MediaSources") or []
            if media_sources:
                src = media_sources[0]
                if src.get("SupportsDirectPlay"):
                    play_method = "DirectPlay"
                elif src.get("SupportsDirectStream"):
                    play_method = "DirectStream"
                elif src.get("TranscodingUrl"):
                    play_method = "Transcode"

        try:
            await self._jellyfin.report_playback_start(
                item_id, resolved_play_session_id, play_method=play_method
            )
        except (httpx.HTTPError, ExternalServiceError) as e:
            logger.error(
                "Failed to report playback start for %s: %s", item_id, e
            )

        return resolved_play_session_id

    async def report_progress(
        self,
        item_id: str,
        play_session_id: str,
        position_seconds: float,
        is_paused: bool,
    ) -> None:
        if not play_session_id:
            return
        position_ticks = int(position_seconds * JELLYFIN_TICKS_PER_SECOND)
        try:
            await self._jellyfin.report_playback_progress(
                item_id, play_session_id, position_ticks, is_paused
            )
        except (httpx.HTTPError, ExternalServiceError) as e:
            logger.warning("Progress report failed for %s: %s", item_id, e)

    async def stop_playback(
        self,
        item_id: str,
        play_session_id: str,
        position_seconds: float,
    ) -> None:
        if not play_session_id:
            return
        position_ticks = int(position_seconds * JELLYFIN_TICKS_PER_SECOND)
        try:
            await self._jellyfin.report_playback_stopped(
                item_id, play_session_id, position_ticks
            )
        except (httpx.HTTPError, ExternalServiceError) as e:
            logger.warning("Stop report failed for %s: %s", item_id, e)

    async def proxy_head(self, item_id: str) -> Response:
        result: StreamProxyResult = await self._jellyfin.proxy_head_stream(item_id)
        return Response(status_code=200, headers=result.headers)

    async def proxy_stream(
        self, item_id: str, range_header: str | None = None
    ) -> StreamingResponse:
        result: StreamProxyResult = await self._jellyfin.proxy_get_stream(
            item_id, range_header=range_header
        )
        return StreamingResponse(
            content=result.body_chunks,
            status_code=result.status_code,
            headers=result.headers,
            media_type=result.media_type,
        )

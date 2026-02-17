import logging

import httpx

from core.exceptions import ExternalServiceError, PlaybackNotAllowedError
from infrastructure.constants import JELLYFIN_TICKS_PER_SECOND
from repositories.jellyfin_repository import JellyfinRepository

logger = logging.getLogger(__name__)


class JellyfinPlaybackService:
    def __init__(self, jellyfin_repo: JellyfinRepository):
        self._jellyfin = jellyfin_repo

    async def start_playback(self, item_id: str) -> str:
        """Report playback start to Jellyfin. Returns play_session_id.

        Handles nullable PlaySessionId and checks for ErrorCode in the
        PlaybackInfoResponse (NotAllowed, NoCompatibleStream, RateLimitExceeded).
        """
        info = await self._jellyfin.get_playback_info(item_id)

        error_code = info.get("ErrorCode")
        if error_code:
            raise PlaybackNotAllowedError(
                f"Jellyfin playback not allowed: {error_code}"
            )

        play_session_id: str | None = info.get("PlaySessionId")
        if not play_session_id:
            logger.warning(
                "Jellyfin returned null PlaySessionId for item %s — "
                "streaming without session reporting",
                item_id,
            )
            return ""

        try:
            await self._jellyfin.report_playback_start(item_id, play_session_id)
        except (httpx.HTTPError, ExternalServiceError) as e:
            logger.error(
                "Failed to report playback start for %s: %s", item_id, e
            )

        return play_session_id

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

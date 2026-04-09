from __future__ import annotations

import logging

from fastapi.responses import Response, StreamingResponse

from repositories.plex_models import StreamProxyResult
from repositories.protocols.plex import PlexRepositoryProtocol

logger = logging.getLogger(__name__)


class PlexPlaybackService:
    def __init__(self, plex_repo: PlexRepositoryProtocol) -> None:
        self._plex = plex_repo

    async def proxy_head(self, part_key: str) -> Response:
        result: StreamProxyResult = await self._plex.proxy_head_stream(part_key)
        return Response(status_code=result.status_code, headers=result.headers)

    async def proxy_stream(
        self, part_key: str, range_header: str | None = None
    ) -> StreamingResponse:
        result: StreamProxyResult = await self._plex.proxy_get_stream(
            part_key, range_header=range_header
        )
        return StreamingResponse(
            content=result.body_chunks,
            status_code=result.status_code,
            headers=result.headers,
            media_type=result.media_type,
        )

    async def scrobble(self, rating_key: str) -> bool:
        try:
            return await self._plex.scrobble(rating_key)
        except Exception:  # noqa: BLE001
            logger.warning("Plex scrobble failed for %s", rating_key, exc_info=True)
            return False

    async def report_now_playing(self, rating_key: str) -> bool:
        try:
            return await self._plex.now_playing(rating_key)
        except Exception:  # noqa: BLE001
            logger.warning("Plex now-playing failed for %s", rating_key, exc_info=True)
            return False

    async def proxy_thumb(self, rating_key: str, size: int = 500) -> tuple[bytes, str]:
        return await self._plex.proxy_thumb(rating_key, size=size)

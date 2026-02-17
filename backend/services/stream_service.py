import asyncio
import logging
import random
from typing import AsyncIterator

import httpx

from core.exceptions import ExternalServiceError, ResourceNotFoundError
from infrastructure.constants import STREAM_CHUNK_SIZE
from infrastructure.resilience.retry import CircuitBreaker
from repositories.jellyfin_repository import JellyfinRepository

logger = logging.getLogger(__name__)

_CODEC_CONTENT_TYPE: dict[str, str] = {
    "aac": "audio/aac",
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "flac": "audio/flac",
    "wav": "audio/wav",
}

_STREAMING_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=None, pool=10.0)
_CONNECT_MAX_ATTEMPTS = 2
_CONNECT_BASE_DELAY = 0.5


class StreamService:
    def __init__(
        self,
        jellyfin_repo: JellyfinRepository,
        http_client: httpx.AsyncClient,
    ):
        self._jellyfin = jellyfin_repo
        self._client = http_client
        self._circuit = CircuitBreaker(
            failure_threshold=3,
            success_threshold=2,
            timeout=30.0,
            name="jellyfin_stream",
        )

    async def stream_jellyfin_audio(
        self,
        item_id: str,
        audio_codec: str = "aac",
        bitrate: int = 128000,
        range_header: str | None = None,
    ) -> tuple[AsyncIterator[bytes], dict[str, str], int]:
        """Proxy audio stream from Jellyfin with retry and circuit breaker."""
        if not self._jellyfin.is_configured():
            raise ExternalServiceError("Jellyfin not configured")

        if self._circuit.is_open():
            raise ExternalServiceError(
                "Jellyfin streaming temporarily unavailable (circuit open)"
            )

        stream_url = self._jellyfin.get_stream_url(item_id, audio_codec, bitrate)
        headers = self._jellyfin.get_auth_headers()
        if range_header:
            headers["Range"] = range_header

        response = await self._connect_with_retry(stream_url, headers, item_id)

        content_type = _CODEC_CONTENT_TYPE.get(audio_codec, "audio/aac")
        resp_headers: dict[str, str] = {"Content-Type": content_type}
        if cl := response.headers.get("Content-Length"):
            resp_headers["Content-Length"] = cl
        if cr := response.headers.get("Content-Range"):
            resp_headers["Content-Range"] = cr
        resp_headers["Accept-Ranges"] = "bytes"

        async def _iter_chunks() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes(chunk_size=STREAM_CHUNK_SIZE):
                    yield chunk
            except httpx.StreamError as exc:
                self._circuit.record_failure()
                logger.error(
                    "Jellyfin stream interrupted mid-transfer",
                    extra={"item_id": item_id, "error": str(exc)},
                )
                raise
            finally:
                await response.aclose()

        return _iter_chunks(), resp_headers, response.status_code

    async def _connect_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        item_id: str,
    ) -> httpx.Response:
        last_exc: Exception | None = None

        for attempt in range(1, _CONNECT_MAX_ATTEMPTS + 1):
            try:
                request = self._client.build_request(
                    "GET", url, headers=headers, timeout=_STREAMING_TIMEOUT
                )
                response = await self._client.send(request, stream=True)
            except httpx.HTTPError as e:
                self._circuit.record_failure()
                last_exc = e
                if attempt < _CONNECT_MAX_ATTEMPTS:
                    delay = _CONNECT_BASE_DELAY * (0.5 + random.random())
                    logger.warning(
                        "Jellyfin stream connect failed, retrying",
                        extra={
                            "item_id": item_id,
                            "attempt": attempt,
                            "delay_s": f"{delay:.2f}",
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                    continue
                raise ExternalServiceError(
                    f"Failed to connect to Jellyfin stream after {attempt} attempts: {e}"
                )

            if response.status_code == 404:
                await response.aclose()
                raise ResourceNotFoundError(
                    f"Audio item {item_id} not found in Jellyfin"
                )

            if response.status_code not in (200, 206):
                body = await response.aread()
                await response.aclose()
                self._circuit.record_failure()
                last_exc = ExternalServiceError(
                    f"Jellyfin stream failed ({response.status_code})",
                    body.decode(errors="replace")[:200],
                )
                if attempt < _CONNECT_MAX_ATTEMPTS:
                    delay = _CONNECT_BASE_DELAY * (0.5 + random.random())
                    logger.warning(
                        "Jellyfin stream bad status, retrying",
                        extra={
                            "item_id": item_id,
                            "attempt": attempt,
                            "status": response.status_code,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_exc

            self._circuit.record_success()
            return response

        raise last_exc or ExternalServiceError("Jellyfin stream connect failed")

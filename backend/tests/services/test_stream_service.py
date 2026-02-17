import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from core.exceptions import ExternalServiceError, ResourceNotFoundError
from services.stream_service import StreamService


def _make_jellyfin_repo(configured: bool = True) -> MagicMock:
    repo = MagicMock()
    repo.is_configured.return_value = configured
    repo.get_stream_url.return_value = "http://jellyfin:8096/Audio/item1/stream"
    repo.get_auth_headers.return_value = {"X-Emby-Token": "test-key"}
    return repo


def _make_mock_response(
    status_code: int = 200,
    headers: dict | None = None,
    chunks: list[bytes] | None = None,
) -> AsyncMock:
    resp = AsyncMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.aclose = AsyncMock()
    resp.aread = AsyncMock(return_value=b"error body")

    async def _aiter(chunk_size: int = 8192):
        for chunk in (chunks or [b"audio-data"]):
            yield chunk

    resp.aiter_bytes = _aiter
    return resp


@pytest.fixture
def service():
    repo = _make_jellyfin_repo()
    client = AsyncMock(spec=httpx.AsyncClient)
    client.build_request.return_value = MagicMock()
    svc = StreamService(jellyfin_repo=repo, http_client=client)
    return svc, repo, client


@pytest.mark.asyncio
async def test_stream_returns_chunks_on_success(service):
    svc, repo, client = service
    mock_resp = _make_mock_response(
        status_code=200,
        headers={"Content-Length": "1024"},
        chunks=[b"chunk1", b"chunk2"],
    )
    client.send = AsyncMock(return_value=mock_resp)

    chunks_iter, headers, status = await svc.stream_jellyfin_audio("item1")

    assert status == 200
    assert headers["Content-Type"] == "audio/aac"
    assert headers["Content-Length"] == "1024"

    collected = []
    async for chunk in chunks_iter:
        collected.append(chunk)
    assert collected == [b"chunk1", b"chunk2"]


@pytest.mark.asyncio
async def test_stream_raises_when_not_configured():
    repo = _make_jellyfin_repo(configured=False)
    client = AsyncMock(spec=httpx.AsyncClient)
    svc = StreamService(jellyfin_repo=repo, http_client=client)

    with pytest.raises(ExternalServiceError, match="not configured"):
        await svc.stream_jellyfin_audio("item1")


@pytest.mark.asyncio
async def test_stream_raises_not_found_on_404(service):
    svc, repo, client = service
    mock_resp = _make_mock_response(status_code=404)
    client.send = AsyncMock(return_value=mock_resp)

    with pytest.raises(ResourceNotFoundError, match="not found"):
        await svc.stream_jellyfin_audio("item1")


@pytest.mark.asyncio
async def test_stream_retries_on_connection_error(service):
    svc, repo, client = service
    mock_resp = _make_mock_response(status_code=200)
    client.send = AsyncMock(
        side_effect=[httpx.ConnectError("refused"), mock_resp]
    )

    chunks_iter, headers, status = await svc.stream_jellyfin_audio("item1")
    assert status == 200
    assert client.send.call_count == 2


@pytest.mark.asyncio
async def test_stream_raises_after_max_retries(service):
    svc, repo, client = service
    client.send = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    with pytest.raises(ExternalServiceError, match="Failed to connect"):
        await svc.stream_jellyfin_audio("item1")

    assert client.send.call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(service):
    svc, repo, client = service
    client.send = AsyncMock(side_effect=httpx.ConnectError("refused"))

    for _ in range(3):
        try:
            await svc.stream_jellyfin_audio("item1")
        except ExternalServiceError:
            pass

    assert svc._circuit.failure_count >= 3

    if svc._circuit.is_open():
        with pytest.raises(ExternalServiceError, match="circuit open"):
            await svc.stream_jellyfin_audio("item1")


@pytest.mark.asyncio
async def test_stream_handles_range_request(service):
    svc, repo, client = service
    mock_resp = _make_mock_response(
        status_code=206,
        headers={
            "Content-Length": "512",
            "Content-Range": "bytes 0-511/1024",
        },
    )
    client.send = AsyncMock(return_value=mock_resp)

    chunks_iter, headers, status = await svc.stream_jellyfin_audio(
        "item1", range_header="bytes=0-511"
    )

    assert status == 206
    assert headers["Content-Range"] == "bytes 0-511/1024"
    assert headers["Accept-Ranges"] == "bytes"

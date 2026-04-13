from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.plex_models import StreamProxyResult
from services.plex_playback_service import PlexPlaybackService


def _make_service() -> tuple[PlexPlaybackService, MagicMock]:
    repo = MagicMock()
    repo.scrobble = AsyncMock(return_value=True)
    repo.now_playing = AsyncMock(return_value=True)
    repo.proxy_thumb = AsyncMock(return_value=(b"\x89PNG", "image/png"))
    repo.proxy_head_stream = AsyncMock(
        return_value=StreamProxyResult(status_code=200, headers={"Content-Type": "audio/flac"}, media_type="audio/flac")
    )
    repo.proxy_get_stream = AsyncMock(
        return_value=StreamProxyResult(status_code=200, headers={}, media_type="audio/mpeg", body_chunks=iter([b"data"]))
    )
    service = PlexPlaybackService(plex_repo=repo)
    return service, repo


class TestScrobble:
    @pytest.mark.asyncio
    async def test_success(self):
        service, repo = _make_service()
        result = await service.scrobble("12345")
        assert result is True
        repo.scrobble.assert_awaited_once_with("12345")

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        service, repo = _make_service()
        repo.scrobble = AsyncMock(side_effect=Exception("network error"))
        result = await service.scrobble("12345")
        assert result is False

    @pytest.mark.asyncio
    async def test_repo_returns_false(self):
        service, repo = _make_service()
        repo.scrobble = AsyncMock(return_value=False)
        result = await service.scrobble("12345")
        assert result is False


class TestReportNowPlaying:
    @pytest.mark.asyncio
    async def test_success(self):
        service, repo = _make_service()
        result = await service.report_now_playing("12345")
        assert result is True
        repo.now_playing.assert_awaited_once_with("12345")

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        service, repo = _make_service()
        repo.now_playing = AsyncMock(side_effect=Exception("timeout"))
        result = await service.report_now_playing("12345")
        assert result is False


class TestProxyThumb:
    @pytest.mark.asyncio
    async def test_delegates_to_repo(self):
        service, repo = _make_service()
        content, ctype = await service.proxy_thumb("123", size=300)
        assert content == b"\x89PNG"
        assert ctype == "image/png"
        repo.proxy_thumb.assert_awaited_once_with("123", size=300)


class TestProxyHead:
    @pytest.mark.asyncio
    async def test_returns_response(self):
        service, _ = _make_service()
        response = await service.proxy_head("/library/parts/1/2/file.flac")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_non_200_status(self):
        service, repo = _make_service()
        repo.proxy_head_stream = AsyncMock(
            return_value=StreamProxyResult(status_code=404, headers={}, media_type=None)
        )
        response = await service.proxy_head("/library/parts/1/2/file.flac")
        assert response.status_code == 404


class TestProxyStream:
    @pytest.mark.asyncio
    async def test_returns_streaming_response(self):
        service, repo = _make_service()

        async def _chunks():
            yield b"audio-data"

        repo.proxy_get_stream = AsyncMock(
            return_value=StreamProxyResult(
                status_code=200,
                headers={"Content-Type": "audio/flac"},
                media_type="audio/flac",
                body_chunks=_chunks(),
            )
        )
        response = await service.proxy_stream("/library/parts/1/2/file.flac")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_passes_range_header(self):
        service, repo = _make_service()

        async def _chunks():
            yield b"partial"

        repo.proxy_get_stream = AsyncMock(
            return_value=StreamProxyResult(
                status_code=206,
                headers={"Content-Range": "bytes 0-100/200"},
                media_type="audio/mpeg",
                body_chunks=_chunks(),
            )
        )
        response = await service.proxy_stream("/part/key", range_header="bytes=0-100")
        repo.proxy_get_stream.assert_awaited_once_with("/part/key", range_header="bytes=0-100")
        assert response.status_code == 206

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import ExternalServiceError
from services.request_service import RequestService


def _make_service(queue_add_result: dict | None = None) -> tuple[RequestService, MagicMock, MagicMock]:
    lidarr_repo = MagicMock()
    request_queue = MagicMock()
    request_history = MagicMock()

    request_queue.add = AsyncMock(return_value=queue_add_result or {"message": "queued", "payload": {}})
    request_queue.get_status = MagicMock(return_value={"queue_size": 0, "processing": False})
    request_history.async_record_request = AsyncMock()

    service = RequestService(lidarr_repo, request_queue, request_history)
    return service, request_queue, request_history


@pytest.mark.asyncio
async def test_request_album_records_history_and_returns_response():
    service, request_queue, request_history = _make_service(
        {
            "message": "Album queued",
            "payload": {
                "id": 42,
                "title": "Album X",
                "foreignAlbumId": "rg-123",
                "artist": {"artistName": "Artist X", "foreignArtistId": "artist-123"},
            },
        }
    )

    response = await service.request_album("rg-123", artist="Fallback Artist", album="Fallback Album", year=2024)

    assert response.success is True
    assert response.message == "Album queued"
    assert isinstance(response.lidarr_response, dict)
    assert response.lidarr_response["id"] == 42

    request_queue.add.assert_awaited_once_with("rg-123")
    request_history.async_record_request.assert_awaited_once()
    kwargs = request_history.async_record_request.await_args.kwargs
    assert kwargs["artist_name"] == "Artist X"
    assert kwargs["album_title"] == "Album X"
    assert kwargs["artist_mbid"] == "artist-123"


@pytest.mark.asyncio
async def test_request_album_wraps_errors():
    service, request_queue, _ = _make_service()
    request_queue.add.side_effect = RuntimeError("boom")

    with pytest.raises(ExternalServiceError):
        await service.request_album("rg-123")


def test_get_queue_status_returns_schema():
    service, request_queue, _ = _make_service()
    request_queue.get_status.return_value = {"queue_size": 3, "processing": True}

    status = service.get_queue_status()

    assert status.queue_size == 3
    assert status.processing is True

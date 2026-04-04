import pytest
from unittest.mock import AsyncMock

from core.exceptions import ExternalServiceError, PlaybackNotAllowedError, ResourceNotFoundError
from infrastructure.constants import BROWSER_AUDIO_DEVICE_PROFILE
from repositories.jellyfin_repository import JellyfinRepository


@pytest.fixture
def repo() -> JellyfinRepository:
    http_client = AsyncMock()
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return JellyfinRepository(
        http_client=http_client,
        cache=cache,
        base_url="http://jellyfin:8096",
        api_key="test-api-key",
        user_id="user-123",
    )


@pytest.mark.asyncio
async def test_get_playback_url_direct_play(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-1",
            "MediaSources": [
                {"SupportsDirectPlay": True, "SupportsDirectStream": True}
            ],
        }
    )

    result = await repo.get_playback_url("item-1")

    assert result.url == "http://jellyfin:8096/Audio/item-1/stream?static=true"
    assert result.seekable is True
    assert result.play_session_id == "sess-1"
    assert result.play_method == "DirectPlay"


@pytest.mark.asyncio
async def test_get_playback_url_transcode(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-2",
            "MediaSources": [
                {
                    "SupportsDirectPlay": False,
                    "SupportsDirectStream": False,
                    "TranscodingUrl": "/Audio/item-2/universal?container=opus&api_key=embedded-key",
                }
            ],
        }
    )

    result = await repo.get_playback_url("item-2")

    assert result.url == "http://jellyfin:8096/Audio/item-2/universal?container=opus&api_key=embedded-key"
    assert result.seekable is False
    assert result.play_session_id == "sess-2"
    assert result.play_method == "Transcode"


@pytest.mark.asyncio
async def test_get_playback_url_direct_stream(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-ds",
            "MediaSources": [
                {"SupportsDirectPlay": False, "SupportsDirectStream": True}
            ],
        }
    )

    result = await repo.get_playback_url("item-direct-stream")

    assert result.url == "http://jellyfin:8096/Audio/item-direct-stream/stream?static=true"
    assert result.seekable is True
    assert result.play_method == "DirectStream"


@pytest.mark.asyncio
async def test_get_playback_url_uses_post_with_device_profile(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-3",
            "MediaSources": [
                {"SupportsDirectPlay": True, "SupportsDirectStream": True}
            ],
        }
    )

    await repo.get_playback_url("item-3")

    repo._request.assert_awaited_once_with(
        "POST",
        "/Items/item-3/PlaybackInfo",
        params={"userId": "user-123"},
        json_data={"DeviceProfile": BROWSER_AUDIO_DEVICE_PROFILE},
    )


@pytest.mark.asyncio
async def test_get_playback_url_not_configured_raises():
    http_client = AsyncMock()
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    unconfigured_repo = JellyfinRepository(
        http_client=http_client,
        cache=cache,
        base_url="",
        api_key="",
    )

    with pytest.raises(ExternalServiceError, match="not configured"):
        await unconfigured_repo.get_playback_url("item-4")


@pytest.mark.asyncio
async def test_proxy_get_stream_validates_url_origin(repo: JellyfinRepository):
    from repositories.jellyfin_models import PlaybackUrlResult

    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-bad",
            "MediaSources": [
                {
                    "SupportsDirectPlay": False,
                    "SupportsDirectStream": False,
                    "TranscodingUrl": "http://evil.example.com/Audio/item-1/stream",
                }
            ],
        }
    )

    with pytest.raises(ExternalServiceError, match="does not match"):
        await repo.proxy_get_stream("item-1")


@pytest.mark.asyncio
async def test_get_playback_url_missing_item_raises(repo: JellyfinRepository):
    repo._request = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundError, match="Playback info not found"):
        await repo.get_playback_url("bad-item")


@pytest.mark.asyncio
async def test_get_playback_url_missing_media_sources_raises(repo: JellyfinRepository):
    repo._request = AsyncMock(return_value={"PlaySessionId": "sess-5", "MediaSources": []})

    with pytest.raises(ExternalServiceError, match="missing media sources"):
        await repo.get_playback_url("item-5")


@pytest.mark.asyncio
async def test_get_playback_url_playback_not_allowed_raises(repo: JellyfinRepository):
    repo._request = AsyncMock(return_value={"ErrorCode": "NotAllowed"})

    with pytest.raises(PlaybackNotAllowedError, match="NotAllowed"):
        await repo.get_playback_url("item-6")


@pytest.mark.asyncio
async def test_get_playback_url_null_play_session_id_defaults_empty(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": None,
            "MediaSources": [
                {"SupportsDirectPlay": True, "SupportsDirectStream": True}
            ],
        }
    )

    result = await repo.get_playback_url("item-7")

    assert result.play_session_id == ""


@pytest.mark.asyncio
async def test_get_playback_url_transcoding_url_keeps_embedded_api_key(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-8",
            "MediaSources": [
                {
                    "SupportsDirectPlay": False,
                    "SupportsDirectStream": False,
                    "TranscodingUrl": "/audio/item-8/stream.opus?ApiKey=embedded&PlaySessionId=sess-8",
                }
            ],
        }
    )

    result = await repo.get_playback_url("item-8")

    assert "ApiKey=embedded" in result.url
    assert result.url.count("ApiKey=") == 1


@pytest.mark.asyncio
async def test_get_playback_url_transcoding_url_absolute_is_used_as_is(repo: JellyfinRepository):
    repo._request = AsyncMock(
        return_value={
            "PlaySessionId": "sess-9",
            "MediaSources": [
                {
                    "SupportsDirectPlay": False,
                    "SupportsDirectStream": False,
                    "TranscodingUrl": "https://jellyfin.example/audio/item-9/stream.opus?ApiKey=embedded",
                }
            ],
        }
    )

    result = await repo.get_playback_url("item-9")

    assert result.url == "https://jellyfin.example/audio/item-9/stream.opus?ApiKey=embedded"

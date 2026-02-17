import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.exceptions import ExternalServiceError, ResourceNotFoundError
from services.local_files_service import LocalFilesService, AUDIO_EXTENSIONS


def _make_mock_cache() -> AsyncMock:
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


def _make_preferences(music_path: str = "/music", lidarr_root: str = "/music") -> MagicMock:
    prefs = MagicMock()
    settings = MagicMock()
    settings.music_path = music_path
    settings.lidarr_root_path = lidarr_root
    prefs.get_local_files_connection.return_value = settings
    return prefs


@pytest.fixture
def service(tmp_path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    lidarr = AsyncMock()
    prefs = _make_preferences(str(music_dir), str(music_dir))
    cache = _make_mock_cache()
    svc = LocalFilesService(
        lidarr_repo=lidarr,
        preferences_service=prefs,
        cache=cache,
    )
    return svc, lidarr, music_dir, cache


@pytest.mark.asyncio
async def test_stream_track_validates_audio_format(service):
    svc, lidarr, music_dir, cache = service
    bad_file = music_dir / "test.txt"
    bad_file.write_text("not audio")

    lidarr.get_track_file = AsyncMock(return_value={"path": str(bad_file)})

    with pytest.raises(ExternalServiceError, match="Unsupported audio format"):
        await svc.stream_track(1)


@pytest.mark.asyncio
async def test_stream_track_serves_valid_file(service):
    svc, lidarr, music_dir, cache = service
    audio_file = music_dir / "song.flac"
    audio_file.write_bytes(b"fLaC" + b"\x00" * 100)

    lidarr.get_track_file = AsyncMock(return_value={"path": str(audio_file)})

    chunks_iter, headers, status = await svc.stream_track(1)
    assert status == 200
    assert headers["Content-Type"] == "audio/flac"

    collected = b""
    async for chunk in chunks_iter:
        collected += chunk
    assert len(collected) == 104


@pytest.mark.asyncio
async def test_stream_track_handles_range_request(service):
    svc, lidarr, music_dir, cache = service
    audio_file = music_dir / "song.mp3"
    audio_file.write_bytes(b"\xff\xfb" + b"\x00" * 998)

    lidarr.get_track_file = AsyncMock(return_value={"path": str(audio_file)})

    chunks_iter, headers, status = await svc.stream_track(
        1, range_header="bytes=0-99"
    )
    assert status == 206
    assert "Content-Range" in headers

    collected = b""
    async for chunk in chunks_iter:
        collected += chunk
    assert len(collected) == 100


@pytest.mark.asyncio
async def test_stream_track_raises_on_missing_file(service):
    svc, lidarr, music_dir, cache = service
    lidarr.get_track_file = AsyncMock(
        return_value={"path": str(music_dir / "nonexistent.flac")}
    )

    with pytest.raises(ResourceNotFoundError, match="not found"):
        await svc.stream_track(1)


@pytest.mark.asyncio
async def test_stream_track_raises_on_path_traversal(service):
    svc, lidarr, music_dir, cache = service
    lidarr.get_track_file = AsyncMock(
        return_value={"path": "/etc/passwd"}
    )

    with pytest.raises(PermissionError, match="outside music directory"):
        await svc.stream_track(1)


@pytest.mark.asyncio
async def test_get_storage_stats_uses_cache(service):
    svc, lidarr, music_dir, cache = service
    cached_data = {
        "total_tracks": 42,
        "total_albums": 5,
        "total_artists": 3,
        "total_size_bytes": 1000000,
        "total_size_human": "976.6 KB",
        "disk_free_bytes": 500000000,
        "disk_free_human": "476.8 MB",
        "format_breakdown": {},
    }
    cache.get = AsyncMock(return_value=cached_data)

    stats = await svc.get_storage_stats()
    assert stats.total_tracks == 42
    cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_get_storage_stats_caches_result(service):
    svc, lidarr, music_dir, cache = service
    audio_file = music_dir / "artist" / "album" / "track.flac"
    audio_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"\x00" * 50)

    stats = await svc.get_storage_stats()
    assert stats.total_tracks == 1
    assert cache.set.called


@pytest.mark.asyncio
async def test_get_albums_caches_lidarr_response(service):
    svc, lidarr, music_dir, cache = service
    lidarr.get_all_albums = AsyncMock(return_value=[
        {
            "id": 1,
            "title": "Test Album",
            "artist": {"artistName": "Test Artist"},
            "statistics": {"trackFileCount": 3},
            "foreignAlbumId": "mbid-123",
            "releaseDate": "2024-01-01",
        }
    ])

    result = await svc.get_albums(limit=10, offset=0)
    assert result.total == 1

    assert cache.set.called
    call_args = cache.set.call_args
    assert call_args[0][0] == "local_files_all_albums"


@pytest.mark.asyncio
async def test_stream_track_handles_suffix_range(service):
    svc, lidarr, music_dir, cache = service
    audio_file = music_dir / "song.mp3"
    audio_file.write_bytes(b"\xff\xfb" + b"\x00" * 998)

    lidarr.get_track_file = AsyncMock(return_value={"path": str(audio_file)})

    chunks_iter, headers, status = await svc.stream_track(
        1, range_header="bytes=-200"
    )
    assert status == 206
    assert "Content-Range" in headers

    collected = b""
    async for chunk in chunks_iter:
        collected += chunk
    assert len(collected) == 200


@pytest.mark.asyncio
async def test_stream_track_fallback_on_malformed_range(service):
    svc, lidarr, music_dir, cache = service
    audio_file = music_dir / "song.mp3"
    audio_file.write_bytes(b"\xff\xfb" + b"\x00" * 998)

    lidarr.get_track_file = AsyncMock(return_value={"path": str(audio_file)})

    chunks_iter, headers, status = await svc.stream_track(
        1, range_header="bytes=abc-xyz"
    )
    assert status == 200
    assert int(headers["Content-Length"]) == 1000


@pytest.mark.asyncio
async def test_stream_track_rejects_invalid_range(service):
    svc, lidarr, music_dir, cache = service
    audio_file = music_dir / "song.mp3"
    audio_file.write_bytes(b"\xff\xfb" + b"\x00" * 98)

    lidarr.get_track_file = AsyncMock(return_value={"path": str(audio_file)})

    with pytest.raises(ExternalServiceError, match="Range not satisfiable"):
        await svc.stream_track(1, range_header="bytes=5000-6000")


@pytest.mark.asyncio
async def test_remap_path_uses_component_matching(tmp_path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    lidarr = AsyncMock()
    prefs = _make_preferences(str(music_dir), "/data/music")
    cache = _make_mock_cache()
    svc = LocalFilesService(
        lidarr_repo=lidarr,
        preferences_service=prefs,
        cache=cache,
    )
    result = svc._remap_path("/data/music2/artist/album/song.flac")
    assert "/data/music2" in str(result) or "music2" in result.parts

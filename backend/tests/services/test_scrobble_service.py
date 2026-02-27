import time

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from api.v1.schemas.scrobble import NowPlayingRequest, ScrobbleRequest
from api.v1.schemas.settings import ScrobbleSettings, LastFmConnectionSettings, ListenBrainzConnectionSettings
from services.scrobble_service import ScrobbleService


def _make_lastfm_settings(enabled: bool = True, has_creds: bool = True) -> LastFmConnectionSettings:
    return LastFmConnectionSettings(
        api_key="key" if has_creds else "",
        shared_secret="secret" if has_creds else "",
        session_key="sk-123" if has_creds else "",
        username="user",
        enabled=enabled,
    )


def _make_lb_settings(enabled: bool = True, has_token: bool = True) -> ListenBrainzConnectionSettings:
    return ListenBrainzConnectionSettings(
        user_token="tok-abc" if has_token else "",
        enabled=enabled,
    )


def _make_service(
    lastfm_enabled: bool = True,
    lb_enabled: bool = True,
    scrobble_lastfm: bool = True,
    scrobble_lb: bool = True,
) -> tuple[ScrobbleService, AsyncMock, AsyncMock, MagicMock]:
    lastfm_repo = AsyncMock()
    lb_repo = AsyncMock()
    prefs = MagicMock()
    prefs.get_scrobble_settings.return_value = ScrobbleSettings(
        scrobble_to_lastfm=scrobble_lastfm,
        scrobble_to_listenbrainz=scrobble_lb,
    )
    prefs.get_lastfm_connection.return_value = _make_lastfm_settings(enabled=lastfm_enabled)
    prefs.get_listenbrainz_connection.return_value = _make_lb_settings(enabled=lb_enabled)
    service = ScrobbleService(lastfm_repo, lb_repo, prefs)
    return service, lastfm_repo, lb_repo, prefs


def _now_playing_req(**overrides) -> NowPlayingRequest:
    defaults = dict(track_name="Song", artist_name="Artist", album_name="Album", duration_ms=200_000)
    defaults.update(overrides)
    return NowPlayingRequest(**defaults)


def _scrobble_req(**overrides) -> ScrobbleRequest:
    defaults = dict(
        track_name="Song",
        artist_name="Artist",
        album_name="Album",
        timestamp=int(time.time()) - 60,
        duration_ms=200_000,
    )
    defaults.update(overrides)
    return ScrobbleRequest(**defaults)


class TestReportNowPlaying:
    @pytest.mark.asyncio
    async def test_dispatches_to_both_services(self):
        service, lastfm, lb, _ = _make_service()
        result = await service.report_now_playing(_now_playing_req())
        assert result.accepted is True
        assert "lastfm" in result.services
        assert "listenbrainz" in result.services
        lastfm.update_now_playing.assert_awaited_once()
        lb.submit_now_playing.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatches_only_to_lastfm(self):
        service, lastfm, lb, _ = _make_service(scrobble_lb=False)
        result = await service.report_now_playing(_now_playing_req())
        assert result.accepted is True
        assert "lastfm" in result.services
        assert "listenbrainz" not in result.services
        lb.submit_now_playing.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatches_only_to_listenbrainz(self):
        service, lastfm, lb, _ = _make_service(scrobble_lastfm=False)
        result = await service.report_now_playing(_now_playing_req())
        assert result.accepted is True
        assert "listenbrainz" in result.services
        assert "lastfm" not in result.services
        lastfm.update_now_playing.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_services_enabled(self):
        service, lastfm, lb, _ = _make_service(scrobble_lastfm=False, scrobble_lb=False)
        result = await service.report_now_playing(_now_playing_req())
        assert result.accepted is False
        assert result.services == {}

    @pytest.mark.asyncio
    async def test_lastfm_failure_isolated(self):
        service, lastfm, lb, _ = _make_service()
        lastfm.update_now_playing.side_effect = RuntimeError("API down")
        result = await service.report_now_playing(_now_playing_req())
        assert result.accepted is True
        assert result.services["lastfm"].success is False
        assert "API down" in (result.services["lastfm"].error or "")
        assert result.services["listenbrainz"].success is True

    @pytest.mark.asyncio
    async def test_all_services_fail(self):
        service, lastfm, lb, _ = _make_service()
        lastfm.update_now_playing.side_effect = RuntimeError("fail1")
        lb.submit_now_playing.side_effect = RuntimeError("fail2")
        result = await service.report_now_playing(_now_playing_req())
        assert result.accepted is False
        assert result.services["lastfm"].success is False
        assert result.services["listenbrainz"].success is False


class TestSubmitScrobble:
    @pytest.mark.asyncio
    async def test_dispatches_to_both_services(self):
        service, lastfm, lb, _ = _make_service()
        result = await service.submit_scrobble(_scrobble_req())
        assert result.accepted is True
        lastfm.scrobble.assert_awaited_once()
        lb.submit_single_listen.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_short_track(self):
        service, lastfm, lb, _ = _make_service()
        result = await service.submit_scrobble(_scrobble_req(duration_ms=15_000))
        assert result.accepted is False
        assert result.services == {}
        lastfm.scrobble.assert_not_awaited()
        lb.submit_single_listen.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_zero_duration_not_skipped(self):
        service, lastfm, lb, _ = _make_service()
        result = await service.submit_scrobble(_scrobble_req(duration_ms=0))
        assert result.accepted is True
        lastfm.scrobble.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedup_blocks_second_submit(self):
        service, lastfm, lb, _ = _make_service()
        ts = int(time.time()) - 60
        req = _scrobble_req(timestamp=ts)
        result1 = await service.submit_scrobble(req)
        assert result1.accepted is True

        req2 = _scrobble_req(timestamp=ts)
        result2 = await service.submit_scrobble(req2)
        assert result2.accepted is True
        assert result2.services == {}
        assert lastfm.scrobble.await_count == 1

    @pytest.mark.asyncio
    async def test_dedup_different_timestamp_allowed(self):
        service, lastfm, lb, _ = _make_service()
        ts = int(time.time()) - 600
        await service.submit_scrobble(_scrobble_req(timestamp=ts))
        await service.submit_scrobble(_scrobble_req(timestamp=ts + 300))
        assert lastfm.scrobble.await_count == 2

    @pytest.mark.asyncio
    async def test_failure_isolation(self):
        service, lastfm, lb, _ = _make_service()
        lastfm.scrobble.side_effect = RuntimeError("network")
        result = await service.submit_scrobble(_scrobble_req())
        assert result.accepted is True
        assert result.services["lastfm"].success is False
        assert result.services["listenbrainz"].success is True

    @pytest.mark.asyncio
    async def test_failed_scrobble_not_deduped(self):
        service, lastfm, lb, _ = _make_service(scrobble_lb=False)
        lastfm.scrobble.side_effect = RuntimeError("fail")
        ts = int(time.time()) - 60
        result1 = await service.submit_scrobble(_scrobble_req(timestamp=ts))
        assert result1.accepted is False

        lastfm.scrobble.side_effect = None
        result2 = await service.submit_scrobble(_scrobble_req(timestamp=ts))
        assert result2.accepted is True

    @pytest.mark.asyncio
    async def test_disabled_lastfm_no_creds(self):
        service, lastfm, lb, _ = _make_service(lastfm_enabled=False)
        result = await service.submit_scrobble(_scrobble_req())
        assert "lastfm" not in result.services
        lastfm.scrobble.assert_not_awaited()


class TestTimestampValidation:
    def test_future_timestamp_rejected(self):
        with pytest.raises(ValueError, match="future"):
            _scrobble_req(timestamp=int(time.time()) + 3600)

    def test_old_timestamp_rejected(self):
        with pytest.raises(ValueError, match="14 days"):
            _scrobble_req(timestamp=int(time.time()) - 15 * 86400)

    def test_valid_timestamp_accepted(self):
        req = _scrobble_req(timestamp=int(time.time()) - 60)
        assert req.timestamp > 0


class TestDedupEviction:
    @pytest.mark.asyncio
    async def test_evicts_when_exceeding_max(self):
        service, _, _, _ = _make_service()
        base_ts = int(time.time()) - 86400
        for i in range(205):
            req = _scrobble_req(artist_name=f"artist-{i}", timestamp=base_ts + i)
            await service.submit_scrobble(req)
        assert len(service._dedup_cache) <= 200

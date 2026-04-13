import asyncio
import logging
import time
from typing import Any

from api.v1.schemas.scrobble import (
    NowPlayingRequest,
    ScrobbleRequest,
    ScrobbleResponse,
    ServiceResult,
)
from repositories.protocols import LastFmRepositoryProtocol, ListenBrainzRepositoryProtocol
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 3600
DEDUP_MAX_ENTRIES = 200
MIN_TRACK_DURATION_MS = 30_000


class ScrobbleService:
    def __init__(
        self,
        lastfm_repo: LastFmRepositoryProtocol,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
    ):
        self._lastfm_repo = lastfm_repo
        self._listenbrainz_repo = listenbrainz_repo
        self._preferences_service = preferences_service
        self._dedup_cache: dict[str, float] = {}

    def _dedup_key(self, artist: str, track: str, timestamp: int) -> str:
        return f"{artist.lower()}::{track.lower()}::{timestamp}"

    def _is_duplicate(self, key: str) -> bool:
        entry_time = self._dedup_cache.get(key)
        if entry_time is None:
            return False
        return (time.time() - entry_time) < DEDUP_TTL_SECONDS

    def _record_dedup(self, key: str) -> None:
        self._dedup_cache[key] = time.time()
        if len(self._dedup_cache) > DEDUP_MAX_ENTRIES:
            now = time.time()
            expired = [
                k for k, v in self._dedup_cache.items()
                if (now - v) >= DEDUP_TTL_SECONDS
            ]
            for k in expired:
                del self._dedup_cache[k]
            if len(self._dedup_cache) > DEDUP_MAX_ENTRIES:
                oldest = sorted(self._dedup_cache, key=self._dedup_cache.get)  # type: ignore[arg-type]
                for k in oldest[: len(self._dedup_cache) - DEDUP_MAX_ENTRIES]:
                    del self._dedup_cache[k]

    def _is_lastfm_enabled(self) -> bool:
        scrobble = self._preferences_service.get_scrobble_settings()
        if not scrobble.scrobble_to_lastfm:
            return False
        lastfm = self._preferences_service.get_lastfm_connection()
        return (
            lastfm.enabled
            and bool(lastfm.api_key)
            and bool(lastfm.shared_secret)
            and bool(lastfm.session_key)
        )

    def _is_listenbrainz_enabled(self) -> bool:
        scrobble = self._preferences_service.get_scrobble_settings()
        if not scrobble.scrobble_to_listenbrainz:
            return False
        lb = self._preferences_service.get_listenbrainz_connection()
        return lb.enabled and bool(lb.user_token)

    async def report_now_playing(
        self, request: NowPlayingRequest
    ) -> ScrobbleResponse:
        tasks: dict[str, Any] = {}
        duration_sec = request.duration_ms // 1000 if request.duration_ms > 0 else 0

        if self._is_lastfm_enabled():
            tasks["lastfm"] = self._lastfm_repo.update_now_playing(
                artist=request.artist_name,
                track=request.track_name,
                album=request.album_name,
                duration=duration_sec,
                mbid=request.mbid,
            )

        if self._is_listenbrainz_enabled():
            tasks["listenbrainz"] = self._listenbrainz_repo.submit_now_playing(
                artist_name=request.artist_name,
                track_name=request.track_name,
                release_name=request.album_name,
                duration_ms=request.duration_ms,
            )

        if not tasks:
            return ScrobbleResponse(accepted=False, services={})

        results_list = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )
        services: dict[str, ServiceResult] = {}
        any_success = False

        for service_name, result in zip(tasks.keys(), results_list):
            if isinstance(result, BaseException):
                logger.warning(
                    "Now playing report failed for %s: %s",
                    service_name,
                    result,
                )
                services[service_name] = ServiceResult(
                    success=False, error=str(result)
                )
            else:
                services[service_name] = ServiceResult(success=True)
                any_success = True

        return ScrobbleResponse(accepted=any_success, services=services)

    async def submit_scrobble(
        self, request: ScrobbleRequest
    ) -> ScrobbleResponse:
        if 0 < request.duration_ms < MIN_TRACK_DURATION_MS:
            logger.debug(
                "Skipping scrobble for short track (%dms): %s - %s",
                request.duration_ms,
                request.artist_name,
                request.track_name,
            )
            return ScrobbleResponse(accepted=False, services={})

        dedup = self._dedup_key(
            request.artist_name, request.track_name, request.timestamp
        )
        if self._is_duplicate(dedup):
            logger.debug(
                "Duplicate scrobble skipped: %s - %s at %d",
                request.artist_name,
                request.track_name,
                request.timestamp,
            )
            return ScrobbleResponse(accepted=True, services={})

        tasks: dict[str, Any] = {}
        duration_sec = request.duration_ms // 1000 if request.duration_ms > 0 else 0

        if self._is_lastfm_enabled():
            tasks["lastfm"] = self._lastfm_repo.scrobble(
                artist=request.artist_name,
                track=request.track_name,
                timestamp=request.timestamp,
                album=request.album_name,
                duration=duration_sec,
                mbid=request.mbid,
            )

        if self._is_listenbrainz_enabled():
            tasks["listenbrainz"] = self._listenbrainz_repo.submit_single_listen(
                artist_name=request.artist_name,
                track_name=request.track_name,
                listened_at=request.timestamp,
                release_name=request.album_name,
                duration_ms=request.duration_ms,
            )

        if not tasks:
            return ScrobbleResponse(accepted=False, services={})

        results_list = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )
        services: dict[str, ServiceResult] = {}
        any_success = False

        for service_name, result in zip(tasks.keys(), results_list):
            if isinstance(result, BaseException):
                logger.warning(
                    "Scrobble submission failed for %s: %s",
                    service_name,
                    result,
                )
                services[service_name] = ServiceResult(
                    success=False, error=str(result)
                )
            else:
                services[service_name] = ServiceResult(success=True)
                any_success = True

        if any_success:
            self._record_dedup(dedup)

        return ScrobbleResponse(accepted=any_success, services=services)

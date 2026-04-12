"""Route tests for now-playing and session endpoints."""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.routes.plex_library import router as plex_router
from api.v1.routes.navidrome_library import router as navidrome_router
from api.v1.routes.jellyfin_library import router as jellyfin_router
from api.v1.schemas.plex import PlexSessionInfo, PlexSessionsResponse
from api.v1.schemas.navidrome import NavidromeNowPlayingEntrySchema, NavidromeNowPlayingResponse
from api.v1.schemas.jellyfin import JellyfinSessionInfo, JellyfinSessionsResponse
from core.dependencies import (
    get_plex_library_service,
    get_navidrome_library_service,
    get_jellyfin_library_service,
    get_plex_repository,
)


class TestPlexSessionsRoute:
    @pytest.fixture
    def _setup(self):
        self.mock_svc = MagicMock()
        self.mock_svc.get_sessions = AsyncMock(return_value=PlexSessionsResponse(sessions=[
            PlexSessionInfo(
                session_id="s1",
                user_name="alice",
                track_title="Song A",
                artist_name="Artist A",
                album_name="Album A",
                cover_url="/api/v1/plex/thumb/200",
                player_device="iPhone",
                player_platform="iOS",
                player_state="playing",
                is_direct_play=True,
                progress_ms=60000,
                duration_ms=180000,
                audio_codec="flac",
                audio_channels=2,
                bitrate=1411,
            )
        ]))
        app = FastAPI()
        app.include_router(plex_router)
        app.dependency_overrides[get_plex_library_service] = lambda: self.mock_svc
        app.dependency_overrides[get_plex_repository] = lambda: MagicMock()
        self.client = TestClient(app)

    def test_sessions_returns_200(self, _setup):
        resp = self.client.get("/plex/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "s1"
        assert data["sessions"][0]["track_title"] == "Song A"

    def test_sessions_empty(self, _setup):
        self.mock_svc.get_sessions = AsyncMock(return_value=PlexSessionsResponse(sessions=[]))
        resp = self.client.get("/plex/sessions")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []


class TestNavidromeNowPlayingRoute:
    @pytest.fixture
    def _setup(self):
        self.mock_svc = MagicMock()
        self.mock_svc.get_now_playing = AsyncMock(return_value=NavidromeNowPlayingResponse(entries=[
            NavidromeNowPlayingEntrySchema(
                user_name="bob",
                minutes_ago=2,
                player_name="Firefox",
                track_name="Song N",
                artist_name="Artist N",
                album_name="Album N",
                album_id="al1",
                cover_art_id="cov1",
                duration_seconds=240,
            )
        ]))
        app = FastAPI()
        app.include_router(navidrome_router)
        app.dependency_overrides[get_navidrome_library_service] = lambda: self.mock_svc
        self.client = TestClient(app)

    def test_now_playing_returns_200(self, _setup):
        resp = self.client.get("/navidrome/now-playing")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["user_name"] == "bob"
        assert data["entries"][0]["track_name"] == "Song N"

    def test_now_playing_empty(self, _setup):
        self.mock_svc.get_now_playing = AsyncMock(
            return_value=NavidromeNowPlayingResponse(entries=[])
        )
        resp = self.client.get("/navidrome/now-playing")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []


class TestJellyfinSessionsRoute:
    @pytest.fixture
    def _setup(self):
        self.mock_svc = MagicMock()
        self.mock_svc.get_sessions = AsyncMock(return_value=JellyfinSessionsResponse(sessions=[
            JellyfinSessionInfo(
                session_id="js1",
                user_name="carol",
                device_name="Chrome",
                client_name="Jellyfin Web",
                track_name="Song J",
                artist_name="Artist J",
                album_name="Album J",
                album_id="jalb1",
                cover_url="/api/v1/jellyfin/image/jitem1",
                position_seconds=60.0,
                duration_seconds=300.0,
                is_paused=False,
                play_method="DirectPlay",
                audio_codec="aac",
                bitrate=256,
            )
        ]))
        app = FastAPI()
        app.include_router(jellyfin_router)
        app.dependency_overrides[get_jellyfin_library_service] = lambda: self.mock_svc
        self.client = TestClient(app)

    def test_sessions_returns_200(self, _setup):
        resp = self.client.get("/jellyfin/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "js1"
        assert data["sessions"][0]["track_name"] == "Song J"
        assert data["sessions"][0]["position_seconds"] == 60.0

    def test_sessions_empty(self, _setup):
        self.mock_svc.get_sessions = AsyncMock(
            return_value=JellyfinSessionsResponse(sessions=[])
        )
        resp = self.client.get("/jellyfin/sessions")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []

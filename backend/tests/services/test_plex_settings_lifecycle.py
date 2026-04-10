from __future__ import annotations

import os
import tempfile

os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.schemas.settings import PlexConnectionSettings
from services.settings_service import SettingsService


def _make_settings_service() -> tuple[SettingsService, MagicMock, MagicMock]:
    cache = MagicMock()
    cache.clear_prefix = AsyncMock()
    prefs = MagicMock()

    service = SettingsService(
        preferences_service=prefs,
        cache=cache,
    )
    return service, cache, prefs


def _patch_plex_dependencies():
    """Return a context manager that patches all dependencies used inside on_plex_settings_changed."""
    mock_repo_class = MagicMock()
    mock_repo_class.reset_circuit_breaker = MagicMock()

    mock_new_repo = MagicMock()
    mock_new_repo.clear_cache = AsyncMock()

    mock_get_repo = MagicMock(return_value=mock_new_repo)
    mock_get_repo.cache_clear = MagicMock()

    mock_get_lib = MagicMock()
    mock_get_lib.cache_clear = MagicMock()

    mock_get_pb = MagicMock()
    mock_get_pb.cache_clear = MagicMock()

    mock_get_home = MagicMock()
    mock_get_home.cache_clear = MagicMock()

    mock_get_charts = MagicMock()
    mock_get_charts.cache_clear = MagicMock()

    mbid_store = MagicMock()
    mbid_store.clear_plex_mbid_indexes = AsyncMock()
    mock_get_mbid = MagicMock(return_value=mbid_store)

    return {
        "repo_class": mock_repo_class,
        "new_repo": mock_new_repo,
        "get_repo": mock_get_repo,
        "get_lib": mock_get_lib,
        "get_pb": mock_get_pb,
        "get_home": mock_get_home,
        "get_charts": mock_get_charts,
        "mbid_store": mbid_store,
        "get_mbid": mock_get_mbid,
    }


class TestOnPlexSettingsChanged:
    @pytest.mark.asyncio
    async def test_resets_caches(self):
        service, cache, _ = _make_settings_service()
        mocks = _patch_plex_dependencies()

        with patch("repositories.plex_repository.PlexRepository", mocks["repo_class"]), \
             patch("core.dependencies.get_plex_repository", mocks["get_repo"]), \
             patch("core.dependencies.get_plex_library_service", mocks["get_lib"]), \
             patch("core.dependencies.get_plex_playback_service", mocks["get_pb"]), \
             patch("core.dependencies.get_home_service", mocks["get_home"]), \
             patch("core.dependencies.get_home_charts_service", mocks["get_charts"]), \
             patch("core.dependencies.get_mbid_store", mocks["get_mbid"]):
            await service.on_plex_settings_changed(enabled=False)

            mocks["repo_class"].reset_circuit_breaker.assert_called_once()
            mocks["get_repo"].cache_clear.assert_called_once()
            mocks["get_lib"].cache_clear.assert_called_once()
            mocks["get_pb"].cache_clear.assert_called_once()
            mocks["new_repo"].clear_cache.assert_awaited_once()
            mocks["mbid_store"].clear_plex_mbid_indexes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_triggers_warmup_when_enabled(self):
        service, cache, _ = _make_settings_service()
        mocks = _patch_plex_dependencies()

        registry = MagicMock()
        registry.is_running.return_value = False

        with patch("repositories.plex_repository.PlexRepository", mocks["repo_class"]), \
             patch("core.dependencies.get_plex_repository", mocks["get_repo"]), \
             patch("core.dependencies.get_plex_library_service", mocks["get_lib"]), \
             patch("core.dependencies.get_plex_playback_service", mocks["get_pb"]), \
             patch("core.dependencies.get_home_service", mocks["get_home"]), \
             patch("core.dependencies.get_home_charts_service", mocks["get_charts"]), \
             patch("core.dependencies.get_mbid_store", mocks["get_mbid"]), \
             patch("core.task_registry.TaskRegistry.get_instance", return_value=registry), \
             patch("core.tasks.warm_plex_mbid_cache", new=AsyncMock()):
            await service.on_plex_settings_changed(enabled=True)
            registry.is_running.assert_called_with("plex-mbid-warmup")

    @pytest.mark.asyncio
    async def test_skips_warmup_if_already_running(self):
        service, cache, _ = _make_settings_service()
        mocks = _patch_plex_dependencies()

        registry = MagicMock()
        registry.is_running.return_value = True

        with patch("repositories.plex_repository.PlexRepository", mocks["repo_class"]), \
             patch("core.dependencies.get_plex_repository", mocks["get_repo"]), \
             patch("core.dependencies.get_plex_library_service", mocks["get_lib"]), \
             patch("core.dependencies.get_plex_playback_service", mocks["get_pb"]), \
             patch("core.dependencies.get_home_service", mocks["get_home"]), \
             patch("core.dependencies.get_home_charts_service", mocks["get_charts"]), \
             patch("core.dependencies.get_mbid_store", mocks["get_mbid"]), \
             patch("core.task_registry.TaskRegistry.get_instance", return_value=registry):
            await service.on_plex_settings_changed(enabled=True)
            registry.register.assert_not_called()


class TestVerifyPlex:
    @pytest.mark.asyncio
    async def test_returns_valid_on_success(self):
        service, _, prefs = _make_settings_service()
        prefs.get_setting.return_value = "client-id"

        mock_repo = MagicMock()
        mock_repo.configure = MagicMock()
        mock_repo.validate_connection = AsyncMock(return_value=(True, "OK"))
        section = MagicMock(key="1", title="Music")
        mock_repo.get_music_libraries = AsyncMock(return_value=[section])

        mock_cls = MagicMock(return_value=mock_repo)
        mock_cls.reset_circuit_breaker = MagicMock()

        with patch("repositories.plex_repository.PlexRepository", mock_cls), \
             patch("core.config.get_settings"), \
             patch("infrastructure.http.client.get_http_client"):
            settings = PlexConnectionSettings(plex_url="http://plex:32400", plex_token="tok")
            result = await service.verify_plex(settings)
            assert result.valid is True
            assert result.libraries == [("1", "Music")]

    @pytest.mark.asyncio
    async def test_returns_invalid_on_connection_failure(self):
        service, _, prefs = _make_settings_service()
        prefs.get_setting.return_value = "client-id"

        mock_repo = MagicMock()
        mock_repo.configure = MagicMock()
        mock_repo.validate_connection = AsyncMock(return_value=(False, "refused"))

        mock_cls = MagicMock(return_value=mock_repo)
        mock_cls.reset_circuit_breaker = MagicMock()

        with patch("repositories.plex_repository.PlexRepository", mock_cls), \
             patch("core.config.get_settings"), \
             patch("infrastructure.http.client.get_http_client"):
            settings = PlexConnectionSettings(plex_url="http://plex:32400", plex_token="tok")
            result = await service.verify_plex(settings)
            assert result.valid is False
            assert result.libraries == []

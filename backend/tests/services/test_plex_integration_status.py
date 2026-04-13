from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.home.integration_helpers import HomeIntegrationHelpers


def _make_plex_conn(enabled=True, url="http://plex:32400", token="tok", library_ids=None):
    conn = MagicMock()
    conn.enabled = enabled
    conn.plex_url = url
    conn.plex_token = token
    conn.music_library_ids = library_ids if library_ids is not None else ["1"]
    return conn


def _make_helpers(**overrides):
    prefs = MagicMock()
    prefs.get_plex_connection.return_value = _make_plex_conn(**overrides)
    prefs.get_jellyfin_connection.return_value = MagicMock(enabled=False)
    prefs.get_navidrome_connection.return_value = MagicMock(enabled=False, navidrome_url="", username="", password="")
    prefs.get_listenbrainz_connection.return_value = MagicMock(enabled=False)
    prefs.is_lastfm_enabled.return_value = False
    prefs.get_lastfm_connection.return_value = MagicMock(enabled=False)
    prefs.get_local_files_connection.return_value = MagicMock(enabled=False, music_path="")
    return HomeIntegrationHelpers(prefs)


class TestIsPlexEnabled:
    def test_enabled_with_all_fields(self):
        helpers = _make_helpers(enabled=True, url="http://plex:32400", token="tok", library_ids=["1"])
        assert helpers.is_plex_enabled() is True

    def test_disabled_when_flag_off(self):
        helpers = _make_helpers(enabled=False)
        assert helpers.is_plex_enabled() is False

    def test_disabled_when_no_url(self):
        helpers = _make_helpers(url="")
        assert helpers.is_plex_enabled() is False

    def test_disabled_when_no_token(self):
        helpers = _make_helpers(token="")
        assert helpers.is_plex_enabled() is False

    def test_disabled_when_no_library_ids(self):
        helpers = _make_helpers(library_ids=[])
        assert helpers.is_plex_enabled() is False

    def test_disabled_when_library_ids_none(self):
        conn = MagicMock()
        conn.enabled = True
        conn.plex_url = "http://plex:32400"
        conn.plex_token = "tok"
        conn.music_library_ids = None
        prefs = MagicMock()
        prefs.get_plex_connection.return_value = conn
        helpers = HomeIntegrationHelpers(prefs)
        assert helpers.is_plex_enabled() is False

import pytest
import time
from unittest.mock import MagicMock, patch

from services.navidrome_library_service import NavidromeLibraryService


@pytest.fixture
def service():
    svc = NavidromeLibraryService.__new__(NavidromeLibraryService)
    svc._mbid_to_navidrome_id = {}
    svc._album_mbid_cache = {}
    svc._dirty = False
    return svc


ALBUM_MBID = "77434d0b-1c5f-48c3-8694-050cb378ebd2"
NAVIDROME_ID = "nav-12345"


def test_invalidate_clears_mbid_to_navidrome_id(service):
    service._mbid_to_navidrome_id[ALBUM_MBID] = NAVIDROME_ID

    service.invalidate_album_cache(ALBUM_MBID)

    assert ALBUM_MBID not in service._mbid_to_navidrome_id


def test_invalidate_clears_positive_album_mbid_cache_entries(service):
    cache_key = "test album:test artist"
    service._album_mbid_cache[cache_key] = ALBUM_MBID

    service.invalidate_album_cache(ALBUM_MBID)

    assert cache_key not in service._album_mbid_cache
    assert service._dirty is True


def test_invalidate_clears_multiple_matching_entries(service):
    service._album_mbid_cache["key1:artist1"] = ALBUM_MBID
    service._album_mbid_cache["key2:artist2"] = ALBUM_MBID
    service._album_mbid_cache["other:other"] = "different-mbid"

    service.invalidate_album_cache(ALBUM_MBID)

    assert "key1:artist1" not in service._album_mbid_cache
    assert "key2:artist2" not in service._album_mbid_cache
    assert "other:other" in service._album_mbid_cache


def test_invalidate_noop_when_not_cached(service):
    service.invalidate_album_cache(ALBUM_MBID)

    assert service._dirty is False


def test_invalidate_leaves_unrelated_entries(service):
    other_mbid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    service._mbid_to_navidrome_id[other_mbid] = "nav-other"
    service._album_mbid_cache["other:artist"] = other_mbid

    service.invalidate_album_cache(ALBUM_MBID)

    assert service._mbid_to_navidrome_id[other_mbid] == "nav-other"
    assert service._album_mbid_cache["other:artist"] == other_mbid

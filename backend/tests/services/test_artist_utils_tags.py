"""Tests for extract_tags deduplication in artist_utils."""

from services.artist_utils import extract_tags


def test_extract_tags_deduplicates():
    mb_artist = {
        "tags": [
            {"name": "rock"},
            {"name": "indie"},
            {"name": "rock"},
            {"name": "alternative"},
            {"name": "indie"},
        ]
    }
    result = extract_tags(mb_artist)
    assert result == ["rock", "indie", "alternative"]


def test_extract_tags_preserves_order():
    mb_artist = {
        "tags": [
            {"name": "electronic"},
            {"name": "ambient"},
            {"name": "electronic"},
            {"name": "downtempo"},
        ]
    }
    result = extract_tags(mb_artist)
    assert result == ["electronic", "ambient", "downtempo"]


def test_extract_tags_respects_limit_after_dedup():
    mb_artist = {
        "tags": [
            {"name": "a"},
            {"name": "b"},
            {"name": "a"},
            {"name": "c"},
            {"name": "d"},
        ]
    }
    result = extract_tags(mb_artist, limit=2)
    assert result == ["a", "b"]


def test_extract_tags_empty():
    assert extract_tags({}) == []
    assert extract_tags({"tags": []}) == []


def test_extract_tags_skips_empty_names():
    mb_artist = {
        "tags": [
            {"name": "rock"},
            {"name": ""},
            {"name": None},
            {},
            {"name": "rock"},
        ]
    }
    result = extract_tags(mb_artist)
    assert result == ["rock"]

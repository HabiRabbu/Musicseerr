"""Tests for GenreIndex enrichment methods."""

import sqlite3
import threading
from typing import Any

import pytest

from infrastructure.persistence.genre_index import GenreIndex


class _NoCloseConnection:
    """Wrapper that prevents .close() from destroying the in-memory database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def close(self) -> None:
        pass  # intentionally a no-op

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


class InMemoryGenreIndex(GenreIndex):
    """GenreIndex backed by an in-memory SQLite database for testing."""

    def __init__(self) -> None:
        self.db_path = None  # type: ignore[assignment]
        self._write_lock = threading.Lock()
        self._real_conn: sqlite3.Connection | None = None
        self._ensure_tables()
        # Create library_artists table that GenreIndex JOINs against
        # (normally owned by LibraryDB but lives in the same SQLite file)
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS library_artists (
                mbid_lower TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                raw_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        if self._real_conn is None:
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._real_conn = conn
        return _NoCloseConnection(self._real_conn)  # type: ignore[return-value]

    def close(self) -> None:
        if self._real_conn:
            self._real_conn.close()
            self._real_conn = None


def _seed_data(
    index: InMemoryGenreIndex,
    artists: list[tuple[str, str]],
    genre_map: dict[str, list[str]],
) -> None:
    """Seed library_artists and artist genre data synchronously.

    artists: [(mbid, name), ...]
    genre_map: {mbid: [genre1, genre2, ...]}
    """
    import json

    conn = index._connect()

    for mbid, name in artists:
        conn.execute(
            "INSERT OR REPLACE INTO library_artists (mbid_lower, name) VALUES (?, ?)",
            (mbid.lower(), name),
        )

    for mbid, genres in genre_map.items():
        mbid_lower = mbid.lower()
        conn.execute(
            """
            INSERT INTO artist_genres (artist_mbid_lower, artist_mbid, genres_json)
            VALUES (?, ?, ?)
            ON CONFLICT(artist_mbid_lower) DO UPDATE SET
                artist_mbid = excluded.artist_mbid,
                genres_json = excluded.genres_json
            """,
            (mbid_lower, mbid, json.dumps(genres)),
        )
        conn.execute(
            "DELETE FROM artist_genre_lookup WHERE artist_mbid_lower = ?",
            (mbid_lower,),
        )
        for genre in genres:
            conn.execute(
                "INSERT OR REPLACE INTO artist_genre_lookup (artist_mbid_lower, genre_lower) VALUES (?, ?)",
                (mbid_lower, genre.strip().lower()),
            )

    conn.commit()


@pytest.fixture
def genre_index() -> InMemoryGenreIndex:
    idx = InMemoryGenreIndex()
    yield idx  # type: ignore[misc]
    idx.close()


class TestGetTopGenres:
    @pytest.mark.asyncio
    async def test_returns_genres_ranked_by_artist_count(self, genre_index: InMemoryGenreIndex) -> None:
        """AC #18: genres ranked by library artist count descending."""
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"), ("a3", "Artist3"),
        ], {
            "a1": ["Rock", "Pop"],
            "a2": ["Rock", "Jazz"],
            "a3": ["Rock"],
        })
        result = await genre_index.get_top_genres(limit=10)
        names = [g for g, _ in result]
        counts = [c for _, c in result]
        assert names[0] == "rock"
        assert counts[0] == 3
        assert counts[0] >= counts[1]
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_respects_limit(self, genre_index: InMemoryGenreIndex) -> None:
        """Limit parameter caps result count."""
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"),
        ], {
            "a1": ["Rock", "Pop", "Jazz"],
            "a2": ["Rock", "Metal"],
        })
        result = await genre_index.get_top_genres(limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_library_returns_empty(self, genre_index: InMemoryGenreIndex) -> None:
        """No library artists → empty result."""
        result = await genre_index.get_top_genres()
        assert result == []

    @pytest.mark.asyncio
    async def test_ties_broken_alphabetically(self, genre_index: InMemoryGenreIndex) -> None:
        """Genres with equal artist counts are ordered alphabetically."""
        _seed_data(genre_index, [
            ("a1", "Artist1"),
        ], {
            "a1": ["Pop", "Jazz"],
        })
        result = await genre_index.get_top_genres(limit=10)
        names = [g for g, _ in result]
        assert names == ["jazz", "pop"]


class TestGetGenreArtistCounts:
    @pytest.mark.asyncio
    async def test_returns_correct_counts(self, genre_index: InMemoryGenreIndex) -> None:
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"), ("a3", "Artist3"),
        ], {
            "a1": ["Rock", "Pop"],
            "a2": ["Rock"],
            "a3": ["Pop", "Jazz"],
        })
        result = await genre_index.get_genre_artist_counts(["Rock", "Pop", "Jazz"])
        assert result["rock"] == 2
        assert result["pop"] == 2
        assert result["jazz"] == 1

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, genre_index: InMemoryGenreIndex) -> None:
        result = await genre_index.get_genre_artist_counts([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_genre_absent_from_result(self, genre_index: InMemoryGenreIndex) -> None:
        """Genres with zero library artists are not in the returned dict."""
        _seed_data(genre_index, [("a1", "Artist1")], {"a1": ["Rock"]})
        result = await genre_index.get_genre_artist_counts(["Rock", "Classical"])
        assert result.get("rock") == 1
        assert "classical" not in result


class TestGetArtistsForGenres:
    @pytest.mark.asyncio
    async def test_returns_correct_artists_per_genre(self, genre_index: InMemoryGenreIndex) -> None:
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"), ("a3", "Artist3"),
        ], {
            "a1": ["Rock", "Pop"],
            "a2": ["Rock"],
            "a3": ["Jazz"],
        })
        result = await genre_index.get_artists_for_genres(["Rock", "Jazz"])
        assert sorted(result["rock"]) == sorted(["a1", "a2"])
        assert result["jazz"] == ["a3"]

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, genre_index: InMemoryGenreIndex) -> None:
        result = await genre_index.get_artists_for_genres([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_genre_not_in_result(self, genre_index: InMemoryGenreIndex) -> None:
        """A genre not in the index should not appear in the result dict."""
        _seed_data(genre_index, [("a1", "Artist1")], {"a1": ["Rock"]})
        result = await genre_index.get_artists_for_genres(["Classical"])
        assert "classical" not in result


class TestGetGenresForArtists:
    @pytest.mark.asyncio
    async def test_returns_genres_for_known_artists(self, genre_index: InMemoryGenreIndex) -> None:
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"),
        ], {
            "a1": ["Rock", "Pop"],
            "a2": ["Jazz"],
        })
        result = await genre_index.get_genres_for_artists(["a1", "a2"])
        assert result["a1"] == ["Rock", "Pop"]
        assert result["a2"] == ["Jazz"]

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, genre_index: InMemoryGenreIndex) -> None:
        result = await genre_index.get_genres_for_artists([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_corrupt_json_skipped(self, genre_index: InMemoryGenreIndex) -> None:
        """Artist with corrupt genres_json is silently skipped."""
        _seed_data(genre_index, [("a1", "Artist1")], {"a1": ["Rock"]})
        conn = genre_index._connect()
        conn.execute(
            "UPDATE artist_genres SET genres_json = 'NOT-JSON' WHERE artist_mbid_lower = 'a1'"
        )
        conn.commit()
        result = await genre_index.get_genres_for_artists(["a1"])
        assert "a1" not in result


class TestGetUnderrepresentedGenres:
    @pytest.mark.asyncio
    async def test_returns_genres_below_threshold(self, genre_index: InMemoryGenreIndex) -> None:
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"), ("a3", "Artist3"),
        ], {
            "a1": ["Rock", "Jazz"],
            "a2": ["Rock", "Blues"],
            "a3": ["Rock"],
        })
        result = await genre_index.get_underrepresented_genres([], threshold=2)
        assert "rock" not in result
        assert "jazz" in result
        assert "blues" in result

    @pytest.mark.asyncio
    async def test_excludes_known_genres(self, genre_index: InMemoryGenreIndex) -> None:
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"),
        ], {
            "a1": ["Rock", "Jazz"],
            "a2": ["Rock"],
        })
        result = await genre_index.get_underrepresented_genres(["Jazz"], threshold=2)
        assert "jazz" not in result

    @pytest.mark.asyncio
    async def test_empty_library_returns_empty(self, genre_index: InMemoryGenreIndex) -> None:
        result = await genre_index.get_underrepresented_genres([], threshold=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_ordered_by_count_descending(self, genre_index: InMemoryGenreIndex) -> None:
        """More-represented-but-still-underrepresented genres come first."""
        _seed_data(genre_index, [
            ("a1", "Artist1"), ("a2", "Artist2"), ("a3", "Artist3"),
            ("a4", "Artist4"), ("a5", "Artist5"),
        ], {
            "a1": ["Rock", "Pop", "Jazz"],
            "a2": ["Rock", "Pop"],
            "a3": ["Rock"],
            "a4": ["Pop"],
            "a5": ["Jazz"],
        })
        result = await genre_index.get_underrepresented_genres([], threshold=4)
        assert len(result) >= 2
        if "jazz" in result and "rock" in result:
            assert result.index("rock") < result.index("jazz")

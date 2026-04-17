"""Domain 2 - Genre indexing persistence."""

import logging
import sqlite3
from typing import Any

from infrastructure.persistence._database import (
    PersistenceBase,
    _decode_json,
    _decode_rows,
    _encode_json,
    _normalize,
)

logger = logging.getLogger(__name__)

LIBRARY_ARTISTS_TABLE = "library_artists"
LIBRARY_ALBUMS_TABLE = "library_albums"


def _normalize_genre(value: str | None) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _clean_genres(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        genre = value.strip()
        if not genre:
            continue
        normalized = _normalize_genre(genre)
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(genre)
    return cleaned


class GenreIndex(PersistenceBase):
    """Owns tables: ``artist_genres``, ``artist_genre_lookup``.

    Genre queries JOIN against ``library_artists`` / ``library_albums``
    which live in the same SQLite database (owned by :class:`LibraryDB`).
    """

    def _ensure_tables(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artist_genres (
                    artist_mbid_lower TEXT PRIMARY KEY,
                    artist_mbid TEXT NOT NULL,
                    genres_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artist_genre_lookup (
                    artist_mbid_lower TEXT NOT NULL,
                    genre_lower TEXT NOT NULL,
                    PRIMARY KEY (artist_mbid_lower, genre_lower)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artist_genre_lookup_genre ON artist_genre_lookup(genre_lower, artist_mbid_lower)"
            )
            self._backfill_artist_genre_lookup(conn)
            conn.commit()
        finally:
            conn.close()

    def _replace_artist_genre_lookup(
        self,
        conn: sqlite3.Connection,
        artist_mbid: str,
        genres: list[str],
    ) -> None:
        artist_mbid_lower = _normalize(artist_mbid)
        conn.execute(
            "DELETE FROM artist_genre_lookup WHERE artist_mbid_lower = ?",
            (artist_mbid_lower,),
        )
        for genre in genres:
            conn.execute(
                "INSERT OR REPLACE INTO artist_genre_lookup (artist_mbid_lower, genre_lower) VALUES (?, ?)",
                (artist_mbid_lower, _normalize_genre(genre)),
            )

    def _backfill_artist_genre_lookup(self, conn: sqlite3.Connection) -> None:
        lookup_count_row = conn.execute(
            "SELECT COUNT(*) AS count FROM artist_genre_lookup"
        ).fetchone()
        if lookup_count_row is not None and int(lookup_count_row["count"] or 0) > 0:
            return

        rows = conn.execute(
            "SELECT artist_mbid, genres_json FROM artist_genres"
        ).fetchall()
        for row in rows:
            try:
                genres = _decode_json(row["genres_json"])
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(genres, list):
                continue
            self._replace_artist_genre_lookup(conn, str(row["artist_mbid"]), _clean_genres(genres))

    async def save_artist_genres(self, artist_genres: dict[str, list[str]]) -> None:
        normalized = {
            mbid: _clean_genres(genres)
            for mbid, genres in artist_genres.items()
            if isinstance(mbid, str) and mbid
        }

        def operation(conn: sqlite3.Connection) -> None:
            for artist_mbid, genres in normalized.items():
                conn.execute(
                    """
                    INSERT INTO artist_genres (artist_mbid_lower, artist_mbid, genres_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(artist_mbid_lower) DO UPDATE SET
                        artist_mbid = excluded.artist_mbid,
                        genres_json = excluded.genres_json
                    """,
                    (_normalize(artist_mbid), artist_mbid, _encode_json(genres)),
                )
                self._replace_artist_genre_lookup(conn, artist_mbid, genres)

        await self._write(operation)

    async def get_artists_by_genre(self, genre: str, limit: int = 50) -> list[dict[str, Any]]:
        needle = _normalize_genre(genre)
        if not needle:
            return []

        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """
                SELECT a.raw_json
                FROM library_artists a
                JOIN artist_genre_lookup g ON a.mbid_lower = g.artist_mbid_lower
                WHERE g.genre_lower = ?
                ORDER BY COALESCE(a.date_added, 0) DESC, a.name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (needle, max(limit, 1)),
            ).fetchall()
            return _decode_rows(rows)

        return await self._read(operation)

    async def get_albums_by_genre(self, genre: str, limit: int = 50) -> list[dict[str, Any]]:
        needle = _normalize_genre(genre)
        if not needle:
            return []

        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """
                SELECT a.raw_json
                FROM library_albums a
                JOIN artist_genre_lookup g ON a.artist_mbid_lower = g.artist_mbid_lower
                WHERE g.genre_lower = ?
                ORDER BY COALESCE(a.date_added, 0) DESC, a.title COLLATE NOCASE ASC
                LIMIT ?
                """,
                (needle, max(limit, 1)),
            ).fetchall()
            return _decode_rows(rows)

        return await self._read(operation)

    async def get_top_genres(self, limit: int = 20) -> list[tuple[str, int]]:
        """Return (genre_lower, artist_count) pairs ordered by count DESC.

        Consumed by ``_build_genre_list()`` in ``homepage_service.py``.
        """

        def operation(conn: sqlite3.Connection) -> list[tuple[str, int]]:
            rows = conn.execute(
                """
                SELECT g.genre_lower,
                       COUNT(DISTINCT g.artist_mbid_lower) AS cnt
                FROM artist_genre_lookup g
                JOIN library_artists la ON la.mbid_lower = g.artist_mbid_lower
                GROUP BY g.genre_lower
                ORDER BY cnt DESC, g.genre_lower ASC
                LIMIT ?
                """,
                (max(limit, 1),),
            ).fetchall()
            return [(row["genre_lower"], int(row["cnt"])) for row in rows]

        return await self._read(operation)

    async def get_genre_artist_counts(self, genres: list[str]) -> dict[str, int]:
        """Return {genre_lower: library_artist_count} for the given genres."""
        normalized = [_normalize_genre(g) for g in genres if g]
        if not normalized:
            return {}

        def operation(conn: sqlite3.Connection) -> dict[str, int]:
            placeholders = ",".join("?" * len(normalized))
            rows = conn.execute(
                f"""
                SELECT g.genre_lower,
                       COUNT(DISTINCT g.artist_mbid_lower) AS cnt
                FROM artist_genre_lookup g
                JOIN library_artists la ON la.mbid_lower = g.artist_mbid_lower
                WHERE g.genre_lower IN ({placeholders})
                GROUP BY g.genre_lower
                """,
                normalized,
            ).fetchall()
            return {row["genre_lower"]: int(row["cnt"]) for row in rows}

        return await self._read(operation)

    async def get_artists_for_genres(self, genres: list[str]) -> dict[str, list[str]]:
        """Return {genre_lower: [artist_mbid_lower, ...]} for library artists."""
        normalized = [_normalize_genre(g) for g in genres if g]
        if not normalized:
            return {}

        def operation(conn: sqlite3.Connection) -> dict[str, list[str]]:
            placeholders = ",".join("?" * len(normalized))
            rows = conn.execute(
                f"""
                SELECT g.genre_lower, g.artist_mbid_lower
                FROM artist_genre_lookup g
                JOIN library_artists la ON la.mbid_lower = g.artist_mbid_lower
                WHERE g.genre_lower IN ({placeholders})
                """,
                normalized,
            ).fetchall()
            result: dict[str, list[str]] = {}
            for row in rows:
                result.setdefault(row["genre_lower"], []).append(row["artist_mbid_lower"])
            return result

        return await self._read(operation)

    async def get_genres_for_artists(self, artist_mbids: list[str]) -> dict[str, list[str]]:
        """Return {artist_mbid_lower: [genre_display_name, ...]} from artist_genres."""
        normalized = [_normalize(m) for m in artist_mbids if m]
        if not normalized:
            return {}

        def operation(conn: sqlite3.Connection) -> dict[str, list[str]]:
            placeholders = ",".join("?" * len(normalized))
            rows = conn.execute(
                f"SELECT artist_mbid_lower, genres_json FROM artist_genres WHERE artist_mbid_lower IN ({placeholders})",
                normalized,
            ).fetchall()
            result: dict[str, list[str]] = {}
            for row in rows:
                try:
                    genres = _decode_json(row["genres_json"])
                except (ValueError, TypeError) as exc:
                    logger.warning(
                        "genre_index.get_genres_for_artists: failed to decode genres_json for artist %s: %s",
                        row["artist_mbid_lower"],
                        exc,
                    )
                    continue
                if isinstance(genres, list):
                    result[row["artist_mbid_lower"]] = _clean_genres(genres)
            return result

        return await self._read(operation)

    async def get_underrepresented_genres(self, known_genres: list[str], threshold: int = 2) -> list[str]:
        """Return genre_lower values with < threshold library artists, excluding known_genres."""
        known_lower = {_normalize_genre(g) for g in known_genres}

        def operation(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """
                SELECT g.genre_lower, COUNT(DISTINCT g.artist_mbid_lower) AS cnt
                FROM artist_genre_lookup g
                JOIN library_artists la ON la.mbid_lower = g.artist_mbid_lower
                GROUP BY g.genre_lower
                HAVING cnt < ? AND cnt >= 1
                ORDER BY cnt DESC
                """,
                (max(threshold, 1),),
            ).fetchall()
            return [row["genre_lower"] for row in rows if row["genre_lower"] not in known_lower]

        return await self._read(operation)

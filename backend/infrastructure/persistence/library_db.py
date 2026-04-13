"""Domain 1: Library state persistence (artists, albums, metadata)."""

import json
import logging
import sqlite3
import time
from typing import Any

from infrastructure.persistence._database import (
    PersistenceBase,
    _decode_json,
    _decode_rows,
    _encode_json,
    _normalize,
)
from infrastructure.serialization import to_jsonable

logger = logging.getLogger(__name__)


def _escape_like(term: str) -> str:
    """Escape SQL LIKE metacharacters so they match literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

# Cross-domain tables cleared during full library resync / clear.
# These belong to other stores but must be reset atomically with library data.
_CROSS_DOMAIN_CLEAR_TABLES = (
    "artist_genres",
    "artist_genre_lookup",
)

_FULL_CLEAR_EXTRA_TABLES = (
    "sync_state",
    "jellyfin_mbid_index",
    "navidrome_album_mbid_index",
    "navidrome_artist_mbid_index",
)


def _safe_delete(conn: sqlite3.Connection, table: str) -> None:
    """DELETE FROM a table that may not exist yet (cross-domain dependency)."""
    try:
        conn.execute(f'DELETE FROM "{table}"')
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            logger.warning("Unexpected error clearing cross-domain table %s: %s", table, exc)


class LibraryDB(PersistenceBase):
    """Owns tables: ``cache_meta``, ``library_artists``, ``library_albums``."""

    def _ensure_tables(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_artists (
                    mbid_lower TEXT PRIMARY KEY,
                    mbid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    album_count INTEGER DEFAULT 0,
                    date_added INTEGER,
                    raw_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_artists_date_added ON library_artists(date_added DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_albums (
                    mbid_lower TEXT PRIMARY KEY,
                    mbid TEXT NOT NULL,
                    artist_mbid TEXT,
                    artist_mbid_lower TEXT,
                    artist_name TEXT,
                    title TEXT NOT NULL,
                    year INTEGER,
                    cover_url TEXT,
                    monitored INTEGER DEFAULT 0,
                    date_added INTEGER,
                    raw_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_albums_artist_mbid ON library_albums(artist_mbid_lower)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_albums_date_added ON library_albums(date_added DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_albums_title ON library_albums(title COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_albums_artist_name ON library_albums(artist_name COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_albums_year ON library_albums(year)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_artists_name ON library_artists(name COLLATE NOCASE)"
            )
            conn.commit()
        finally:
            conn.close()

    async def save_library(self, artists: list[Any], albums: list[Any]) -> None:
        builtins_artists = [to_jsonable(artist) for artist in artists]
        builtins_albums = [to_jsonable(album) for album in albums]
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM library_artists")
            conn.execute("DELETE FROM library_albums")
            for tbl in _CROSS_DOMAIN_CLEAR_TABLES:
                _safe_delete(conn, tbl)

            artist_rows = []
            for artist in builtins_artists:
                if not isinstance(artist, dict):
                    continue
                mbid = artist.get("mbid")
                if not isinstance(mbid, str) or not mbid:
                    continue
                artist_rows.append((
                    _normalize(mbid),
                    mbid,
                    str(artist.get("name") or "Unknown"),
                    int(artist.get("album_count") or 0),
                    artist.get("date_added"),
                    _encode_json(artist),
                ))
            if artist_rows:
                conn.executemany(
                    "INSERT INTO library_artists (mbid_lower, mbid, name, album_count, date_added, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
                    artist_rows,
                )

            album_rows = []
            for album in builtins_albums:
                if not isinstance(album, dict):
                    continue
                mbid = album.get("mbid")
                if not isinstance(mbid, str) or not mbid:
                    continue
                artist_mbid = album.get("artist_mbid")
                album_rows.append((
                    _normalize(mbid),
                    mbid,
                    artist_mbid,
                    _normalize(artist_mbid if isinstance(artist_mbid, str) else None),
                    album.get("artist_name"),
                    str(album.get("title") or "Unknown Album"),
                    album.get("year"),
                    album.get("cover_url"),
                    1 if bool(album.get("monitored", True)) else 0,
                    album.get("date_added"),
                    _encode_json(album),
                ))
            if album_rows:
                conn.executemany(
                    """
                    INSERT INTO library_albums (
                        mbid_lower, mbid, artist_mbid, artist_mbid_lower, artist_name,
                        title, year, cover_url, monitored, date_added, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    album_rows,
                )

            conn.execute(
                "INSERT INTO cache_meta (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                ("last_library_sync", str(now), now),
            )

        await self._write(operation)

    async def upsert_album(self, album: dict[str, Any]) -> None:
        mbid = album.get("mbid")
        if not isinstance(mbid, str) or not mbid:
            return
        artist_mbid = album.get("artist_mbid")
        raw_json = _encode_json(album)

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO library_albums (
                    mbid_lower, mbid, artist_mbid, artist_mbid_lower, artist_name,
                    title, year, cover_url, monitored, date_added, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mbid_lower) DO UPDATE SET
                    artist_mbid = excluded.artist_mbid,
                    artist_mbid_lower = excluded.artist_mbid_lower,
                    artist_name = excluded.artist_name,
                    title = excluded.title,
                    year = excluded.year,
                    cover_url = excluded.cover_url,
                    monitored = excluded.monitored,
                    date_added = excluded.date_added,
                    raw_json = excluded.raw_json
                """,
                (
                    _normalize(mbid),
                    mbid,
                    artist_mbid,
                    _normalize(artist_mbid if isinstance(artist_mbid, str) else None),
                    album.get("artist_name"),
                    str(album.get("title") or "Unknown Album"),
                    album.get("year"),
                    album.get("cover_url"),
                    1 if bool(album.get("monitored", True)) else 0,
                    album.get("date_added"),
                    raw_json,
                ),
            )

        await self._write(operation)

    async def get_artists(self, limit: int | None = None) -> list[dict[str, Any]]:
        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            query = "SELECT raw_json FROM library_artists ORDER BY COALESCE(date_added, 0) DESC, name COLLATE NOCASE ASC"
            params: tuple[object, ...] = ()
            if limit is not None:
                query += " LIMIT ?"
                params = (limit,)
            rows = conn.execute(query, params).fetchall()
            return _decode_rows(rows)

        return await self._read(operation)

    async def get_albums(self) -> list[dict[str, Any]]:
        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT raw_json FROM library_albums ORDER BY COALESCE(date_added, 0) DESC, title COLLATE NOCASE ASC"
            ).fetchall()
            return _decode_rows(rows)

        return await self._read(operation)

    _ALBUM_SORT_COLUMNS = {
        "date_added": "COALESCE(date_added, 0)",
        "title": "title COLLATE NOCASE",
        "artist": "artist_name COLLATE NOCASE",
        "year": "COALESCE(year, 0)",
    }

    _ARTIST_SORT_COLUMNS = {
        "name": "name COLLATE NOCASE",
        "album_count": "album_count",
        "date_added": "COALESCE(date_added, 0)",
    }

    async def get_albums_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "date_added",
        sort_order: str = "desc",
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        sort_col = self._ALBUM_SORT_COLUMNS.get(sort_by, "COALESCE(date_added, 0)")
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        def operation(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], int]:
            where = ""
            params: list[object] = []
            if search:
                term = f"%{_escape_like(search)}%"
                where = "WHERE (artist_name LIKE ? ESCAPE '\\' COLLATE NOCASE OR title LIKE ? ESCAPE '\\' COLLATE NOCASE)"
                params = [term, term]

            count_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM library_albums {where}", params
            ).fetchone()
            total = int(count_row["cnt"]) if count_row else 0

            rows = conn.execute(
                f"SELECT raw_json FROM library_albums {where} ORDER BY {sort_col} {direction}, title COLLATE NOCASE ASC, mbid_lower ASC LIMIT ? OFFSET ?",
                [*params, max(limit, 1), max(offset, 0)],
            ).fetchall()
            return _decode_rows(rows), total

        return await self._read(operation)

    async def get_artists_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "name",
        sort_order: str = "asc",
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        sort_col = self._ARTIST_SORT_COLUMNS.get(sort_by, "name COLLATE NOCASE")
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        def operation(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], int]:
            where = ""
            params: list[object] = []
            if search:
                term = f"%{_escape_like(search)}%"
                where = "WHERE name LIKE ? ESCAPE '\\' COLLATE NOCASE"
                params = [term]

            count_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM library_artists {where}", params
            ).fetchone()
            total = int(count_row["cnt"]) if count_row else 0

            rows = conn.execute(
                f"SELECT raw_json FROM library_artists {where} ORDER BY {sort_col} {direction}, name COLLATE NOCASE ASC, mbid_lower ASC LIMIT ? OFFSET ?",
                [*params, max(limit, 1), max(offset, 0)],
            ).fetchall()
            return _decode_rows(rows), total

        return await self._read(operation)

    async def get_recently_added(self, limit: int = 20) -> list[dict[str, Any]]:
        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT raw_json FROM library_albums ORDER BY COALESCE(date_added, 0) DESC, title COLLATE NOCASE ASC LIMIT ?",
                (max(limit, 1),),
            ).fetchall()
            return _decode_rows(rows)

        return await self._read(operation)

    async def get_album_by_mbid(self, musicbrainz_id: str) -> dict[str, Any] | None:
        normalized_mbid = _normalize(musicbrainz_id)

        def operation(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT raw_json FROM library_albums WHERE mbid_lower = ?",
                (normalized_mbid,),
            ).fetchone()
            if row is None:
                return None
            try:
                payload = _decode_json(row["raw_json"])
            except (json.JSONDecodeError, TypeError):
                return None
            return payload if isinstance(payload, dict) else None

        return await self._read(operation)

    async def get_all_album_mbids(self) -> set[str]:
        def operation(conn: sqlite3.Connection) -> set[str]:
            rows = conn.execute("SELECT mbid FROM library_albums").fetchall()
            return {str(row["mbid"]) for row in rows if row["mbid"]}

        return await self._read(operation)

    async def get_all_artist_mbids(self) -> set[str]:
        def operation(conn: sqlite3.Connection) -> set[str]:
            rows = conn.execute("SELECT mbid FROM library_artists").fetchall()
            return {str(row["mbid"]) for row in rows if row["mbid"]}

        return await self._read(operation)

    async def get_all_albums_for_matching(self) -> list[tuple[str, str, str, str]]:
        """Return (title, artist_name, album_mbid, artist_mbid) for all library albums."""

        def operation(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
            rows = conn.execute(
                "SELECT title, artist_name, mbid, COALESCE(artist_mbid, '') AS artist_mbid FROM library_albums"
            ).fetchall()
            return [
                (str(row["title"]), str(row["artist_name"] or ""), str(row["mbid"]), str(row["artist_mbid"]))
                for row in rows
                if row["title"] and row["mbid"]
            ]

        return await self._read(operation)

    async def get_stats(self) -> dict[str, Any]:
        def operation(conn: sqlite3.Connection) -> dict[str, Any]:
            artist_row = conn.execute("SELECT COUNT(*) AS count FROM library_artists").fetchone()
            album_row = conn.execute("SELECT COUNT(*) AS count FROM library_albums").fetchone()
            sync_row = conn.execute("SELECT value FROM cache_meta WHERE key = 'last_library_sync'").fetchone()
            last_sync = None
            if sync_row is not None:
                try:
                    last_sync = float(sync_row["value"])
                except (TypeError, ValueError):
                    last_sync = None
            db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                "artist_count": int(artist_row["count"] if artist_row is not None else 0),
                "album_count": int(album_row["count"] if album_row is not None else 0),
                "db_size_bytes": db_size_bytes,
                "last_sync": last_sync,
            }

        return await self._read(operation)

    async def clear(self) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM library_artists")
            conn.execute("DELETE FROM library_albums")
            for tbl in _CROSS_DOMAIN_CLEAR_TABLES + _FULL_CLEAR_EXTRA_TABLES:
                _safe_delete(conn, tbl)
            conn.execute("DELETE FROM cache_meta WHERE key = 'last_library_sync'")

        await self._write(operation)

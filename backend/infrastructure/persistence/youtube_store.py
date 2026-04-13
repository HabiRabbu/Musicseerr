"""Domain 3 - YouTube link persistence."""

import sqlite3
from typing import Any

from infrastructure.persistence._database import PersistenceBase
from infrastructure.serialization import to_jsonable


class YouTubeStore(PersistenceBase):
    """Owns tables: ``youtube_links``, ``youtube_track_links``."""

    def _ensure_tables(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS youtube_links (
                    album_id TEXT PRIMARY KEY,
                    video_id TEXT,
                    album_name TEXT NOT NULL,
                    artist_name TEXT NOT NULL,
                    embed_url TEXT,
                    cover_url TEXT,
                    created_at TEXT NOT NULL,
                    is_manual INTEGER DEFAULT 0,
                    track_count INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS youtube_track_links (
                    album_id TEXT NOT NULL,
                    track_number INTEGER NOT NULL,
                    disc_number INTEGER NOT NULL DEFAULT 1,
                    album_name TEXT NOT NULL,
                    track_name TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    artist_name TEXT NOT NULL,
                    embed_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (album_id, disc_number, track_number)
                )
                """
            )
            self._migrate_youtube_links(conn)
            self._migrate_youtube_track_links(conn)
            conn.commit()
        finally:
            conn.close()

    def _migrate_youtube_links(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(youtube_links)").fetchall()

        if not rows:
            # Orphan recovery: main table missing but _old exists from interrupted migration
            old_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='youtube_links_old'"
            ).fetchone()
            if old_exists:
                conn.execute("ALTER TABLE youtube_links_old RENAME TO youtube_links")
                rows = conn.execute("PRAGMA table_info(youtube_links)").fetchall()
            else:
                return

        col_names = {row["name"] for row in rows}
        video_notnull = any(row["name"] == "video_id" and row["notnull"] for row in rows)
        needs_track_count = "track_count" not in col_names

        if not video_notnull and not needs_track_count:
            return

        if video_notnull:
            conn.execute("ALTER TABLE youtube_links RENAME TO youtube_links_old")
            conn.execute(
                """
                CREATE TABLE youtube_links (
                    album_id TEXT PRIMARY KEY,
                    video_id TEXT,
                    album_name TEXT NOT NULL,
                    artist_name TEXT NOT NULL,
                    embed_url TEXT,
                    cover_url TEXT,
                    created_at TEXT NOT NULL,
                    is_manual INTEGER DEFAULT 0,
                    track_count INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                INSERT INTO youtube_links
                    (album_id, video_id, album_name, artist_name, embed_url, cover_url, created_at, is_manual, track_count)
                SELECT album_id, video_id, album_name, artist_name, embed_url, cover_url, created_at, is_manual, 0
                FROM youtube_links_old
                """
            )
            conn.execute("DROP TABLE youtube_links_old")
        elif needs_track_count:
            conn.execute("ALTER TABLE youtube_links ADD COLUMN track_count INTEGER DEFAULT 0")

        conn.execute(
            """
            UPDATE youtube_links
            SET track_count = (
                SELECT COUNT(*) FROM youtube_track_links
                WHERE youtube_track_links.album_id = youtube_links.album_id
            )
            WHERE EXISTS (
                SELECT 1 FROM youtube_track_links
                WHERE youtube_track_links.album_id = youtube_links.album_id
            )
            """
        )

    def _migrate_youtube_track_links(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(youtube_track_links)").fetchall()
        if not rows:
            # Orphan recovery: main table missing but _old exists from interrupted migration
            old_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='youtube_track_links_old'"
            ).fetchone()
            if old_exists:
                conn.execute("ALTER TABLE youtube_track_links_old RENAME TO youtube_track_links")
                rows = conn.execute("PRAGMA table_info(youtube_track_links)").fetchall()
            else:
                return

        col_names = {row["name"] for row in rows}
        if "disc_number" in col_names:
            return

        conn.execute("ALTER TABLE youtube_track_links RENAME TO youtube_track_links_old")
        conn.execute(
            """
            CREATE TABLE youtube_track_links (
                album_id TEXT NOT NULL,
                track_number INTEGER NOT NULL,
                disc_number INTEGER NOT NULL DEFAULT 1,
                album_name TEXT NOT NULL,
                track_name TEXT NOT NULL,
                video_id TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                embed_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (album_id, disc_number, track_number)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO youtube_track_links (
                album_id, track_number, disc_number, album_name, track_name,
                video_id, artist_name, embed_url, created_at
            )
            SELECT album_id, track_number, 1, album_name, track_name,
                   video_id, artist_name, embed_url, created_at
            FROM youtube_track_links_old
            """
        )
        conn.execute("DROP TABLE youtube_track_links_old")

    async def save_youtube_link(self, **payload: Any) -> None:
        builtins = to_jsonable(payload)

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO youtube_links (
                    album_id, video_id, album_name, artist_name,
                    embed_url, cover_url, created_at, is_manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(album_id) DO UPDATE SET
                    video_id = excluded.video_id,
                    album_name = excluded.album_name,
                    artist_name = excluded.artist_name,
                    embed_url = excluded.embed_url,
                    cover_url = excluded.cover_url,
                    created_at = excluded.created_at,
                    is_manual = excluded.is_manual
                """,
                (
                    builtins["album_id"],
                    builtins["video_id"],
                    builtins["album_name"],
                    builtins["artist_name"],
                    builtins["embed_url"],
                    builtins.get("cover_url"),
                    builtins["created_at"],
                    1 if bool(builtins.get("is_manual")) else 0,
                ),
            )

        await self._write(operation)

    async def ensure_youtube_album_entry(
        self,
        album_id: str,
        album_name: str,
        artist_name: str,
        cover_url: str | None,
        created_at: str,
    ) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO youtube_links (
                    album_id, video_id, album_name, artist_name,
                    embed_url, cover_url, created_at, is_manual, track_count
                ) VALUES (
                    ?, NULL, ?, ?, NULL, ?, ?, 0,
                    (SELECT COUNT(*) FROM youtube_track_links WHERE album_id = ?)
                )
                ON CONFLICT(album_id) DO UPDATE SET
                    track_count = (SELECT COUNT(*) FROM youtube_track_links WHERE album_id = excluded.album_id),
                    cover_url = COALESCE(excluded.cover_url, youtube_links.cover_url)
                """,
                (album_id, album_name, artist_name, cover_url, created_at, album_id),
            )

        await self._write(operation)

    async def get_youtube_link(self, album_id: str) -> dict[str, Any] | None:
        def operation(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute("SELECT * FROM youtube_links WHERE album_id = ?", (album_id,)).fetchone()
            if row is None:
                return None
            return {
                "album_id": row["album_id"],
                "video_id": row["video_id"],
                "album_name": row["album_name"],
                "artist_name": row["artist_name"],
                "embed_url": row["embed_url"],
                "cover_url": row["cover_url"],
                "created_at": row["created_at"],
                "is_manual": bool(row["is_manual"]),
                "track_count": row["track_count"] or 0,
            }

        return await self._read(operation)

    async def get_all_youtube_links(self) -> list[dict[str, Any]]:
        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """
                SELECT yl.*,
                       (SELECT COUNT(*) FROM youtube_track_links WHERE album_id = yl.album_id) AS live_track_count
                FROM youtube_links yl
                ORDER BY yl.created_at DESC
                """
            ).fetchall()
            return [
                {
                    "album_id": row["album_id"],
                    "video_id": row["video_id"],
                    "album_name": row["album_name"],
                    "artist_name": row["artist_name"],
                    "embed_url": row["embed_url"],
                    "cover_url": row["cover_url"],
                    "created_at": row["created_at"],
                    "is_manual": bool(row["is_manual"]),
                    "track_count": row["live_track_count"],
                }
                for row in rows
            ]

        return await self._read(operation)

    async def delete_youtube_link(self, album_id: str) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM youtube_track_links WHERE album_id = ?", (album_id,))
            conn.execute("DELETE FROM youtube_links WHERE album_id = ?", (album_id,))
        await self._write(operation)

    async def delete_orphaned_track_links(self) -> int:
        def operation(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                "DELETE FROM youtube_track_links "
                "WHERE album_id NOT IN (SELECT album_id FROM youtube_links) "
                "AND datetime(created_at) < datetime('now', '-1 hour')"
            )
            return cursor.rowcount
        return await self._write(operation)

    async def save_youtube_track_link(self, **payload: Any) -> None:
        builtins = to_jsonable(payload)

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO youtube_track_links (
                    album_id, track_number, disc_number, album_name, track_name,
                    video_id, artist_name, embed_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(album_id, disc_number, track_number) DO UPDATE SET
                    album_name = excluded.album_name,
                    track_name = excluded.track_name,
                    video_id = excluded.video_id,
                    artist_name = excluded.artist_name,
                    embed_url = excluded.embed_url,
                    created_at = excluded.created_at
                """,
                (
                    builtins["album_id"],
                    int(builtins["track_number"]),
                    int(builtins.get("disc_number", 1)),
                    builtins["album_name"],
                    builtins["track_name"],
                    builtins["video_id"],
                    builtins["artist_name"],
                    builtins["embed_url"],
                    builtins["created_at"],
                ),
            )

        await self._write(operation)

    async def save_youtube_track_links_batch(self, album_id: str, payloads: list[dict[str, Any]]) -> None:
        normalized_payloads = [payload for payload in payloads if isinstance(payload, dict)]

        def operation(conn: sqlite3.Connection) -> None:
            for payload in normalized_payloads:
                conn.execute(
                    """
                    INSERT INTO youtube_track_links (
                        album_id, track_number, disc_number, album_name, track_name,
                        video_id, artist_name, embed_url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(album_id, disc_number, track_number) DO UPDATE SET
                        album_name = excluded.album_name,
                        track_name = excluded.track_name,
                        video_id = excluded.video_id,
                        artist_name = excluded.artist_name,
                        embed_url = excluded.embed_url,
                        created_at = excluded.created_at
                    """,
                    (
                        album_id,
                        int(payload["track_number"]),
                        int(payload.get("disc_number", 1)),
                        payload["album_name"],
                        payload["track_name"],
                        payload["video_id"],
                        payload["artist_name"],
                        payload["embed_url"],
                        payload["created_at"],
                    ),
                )

        await self._write(operation)

    async def get_youtube_track_links(self, album_id: str) -> list[dict[str, Any]]:
        def operation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT * FROM youtube_track_links WHERE album_id = ? ORDER BY disc_number ASC, track_number ASC",
                (album_id,),
            ).fetchall()
            return [
                {
                    "album_id": row["album_id"],
                    "track_number": row["track_number"],
                    "disc_number": row["disc_number"],
                    "album_name": row["album_name"],
                    "track_name": row["track_name"],
                    "video_id": row["video_id"],
                    "artist_name": row["artist_name"],
                    "embed_url": row["embed_url"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

        return await self._read(operation)

    async def count_youtube_track_links(self, album_id: str) -> int:
        def operation(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM youtube_track_links WHERE album_id = ?",
                (album_id,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

        return await self._read(operation)

    async def update_youtube_link_track_count(self, album_id: str) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                UPDATE youtube_links
                SET track_count = (SELECT COUNT(*) FROM youtube_track_links WHERE album_id = ?)
                WHERE album_id = ?
                """,
                (album_id, album_id),
            )

        await self._write(operation)

    async def delete_youtube_track_link(self, album_id: str, disc_number: int, track_number: int) -> None:
        await self._write(
            lambda conn: conn.execute(
                "DELETE FROM youtube_track_links WHERE album_id = ? AND disc_number = ? AND track_number = ?",
                (album_id, disc_number, track_number),
            )
        )

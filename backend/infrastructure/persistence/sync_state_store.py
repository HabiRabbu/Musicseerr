"""Domain 5: Sync lifecycle persistence."""

import sqlite3
import time
from typing import Any

from infrastructure.persistence._database import (
    PersistenceBase,
    _decode_json,
    _encode_json,
    _normalize,
)
from infrastructure.serialization import to_jsonable


class SyncStateStore(PersistenceBase):
    """Owns tables: ``sync_state``, ``processed_items``."""

    def _ensure_tables(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_items (
                    item_type TEXT NOT NULL,
                    mbid_lower TEXT NOT NULL,
                    mbid TEXT NOT NULL,
                    PRIMARY KEY (item_type, mbid_lower)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    async def save_sync_state(self, **state: Any) -> None:
        payload = to_jsonable(state)
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO sync_state (singleton, state_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (_encode_json(payload), now),
            )

        await self._write(operation)

    async def get_sync_state(self) -> dict[str, Any] | None:
        def operation(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute("SELECT state_json FROM sync_state WHERE singleton = 1").fetchone()
            if row is None:
                return None
            payload = _decode_json(row["state_json"])
            return payload if isinstance(payload, dict) else None

        return await self._read(operation)

    async def clear_sync_state(self) -> None:
        await self._write(lambda conn: conn.execute("DELETE FROM sync_state WHERE singleton = 1"))

    async def get_processed_items(self, item_type: str) -> set[str]:
        def operation(conn: sqlite3.Connection) -> set[str]:
            rows = conn.execute(
                "SELECT mbid FROM processed_items WHERE item_type = ?",
                (item_type,),
            ).fetchall()
            return {str(row["mbid"]) for row in rows if row["mbid"]}

        return await self._read(operation)

    async def mark_items_processed_batch(self, item_type: str, mbids: list[str]) -> None:
        normalized = [(item_type, _normalize(mbid), mbid) for mbid in mbids if isinstance(mbid, str) and mbid]

        def operation(conn: sqlite3.Connection) -> None:
            conn.executemany(
                "INSERT OR REPLACE INTO processed_items (item_type, mbid_lower, mbid) VALUES (?, ?, ?)",
                normalized,
            )

        await self._write(operation)

    async def clear_processed_items(self) -> None:
        await self._write(lambda conn: conn.execute("DELETE FROM processed_items"))

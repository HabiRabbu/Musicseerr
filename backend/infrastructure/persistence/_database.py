"""Shared SQLite infrastructure for all persistence stores."""

import asyncio
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def _encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _decode_json(text: str) -> Any:
    return json.loads(text)


def _normalize(value: str | None) -> str:
    return value.lower() if isinstance(value, str) else ""


def _decode_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    decoded: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = _decode_json(row["raw_json"])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(payload, dict):
            decoded.append(payload)
    return decoded


class PersistenceBase:
    """Shared base for all domain-specific SQLite stores.

    All stores receive the *same* ``db_path`` and ``write_lock`` so they
    operate on a single database file with serialised writes.
    """

    def __init__(self, db_path: Path, write_lock: threading.Lock) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = write_lock
        with self._write_lock:
            self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _execute(self, operation: Any, write: bool) -> Any:
        if write:
            with self._write_lock:
                conn = self._connect()
                try:
                    result = operation(conn)
                    conn.commit()
                    return result
                finally:
                    conn.close()

        conn = self._connect()
        try:
            return operation(conn)
        finally:
            conn.close()

    async def _read(self, operation: Any) -> Any:
        return await asyncio.to_thread(self._execute, operation, False)

    async def _write(self, operation: Any) -> Any:
        return await asyncio.to_thread(self._execute, operation, True)

    def _ensure_tables(self) -> None:
        raise NotImplementedError

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class QueueStore:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from core.config import get_settings
            db_path = get_settings().queue_db_path
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_tables(self) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS pending_jobs (
                        id TEXT PRIMARY KEY,
                        album_mbid TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        status TEXT NOT NULL DEFAULT 'pending'
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_mbid_active
                        ON pending_jobs(album_mbid) WHERE status = 'pending';

                    CREATE TABLE IF NOT EXISTS dead_letters (
                        id TEXT PRIMARY KEY,
                        album_mbid TEXT NOT NULL,
                        error_message TEXT NOT NULL DEFAULT '',
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        max_retries INTEGER NOT NULL DEFAULT 3,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        last_attempted_at TEXT NOT NULL DEFAULT (datetime('now')),
                        status TEXT NOT NULL DEFAULT 'pending'
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    def enqueue(self, job_id: str, album_mbid: str) -> bool:
        """Persist a job. Returns True if inserted, False if duplicate MBID already pending."""
        with self._write_lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO pending_jobs (id, album_mbid) VALUES (?, ?)",
                    (job_id, album_mbid),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def dequeue(self, job_id: str) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM pending_jobs WHERE id = ?", (job_id,))
                conn.commit()
            finally:
                conn.close()

    def mark_processing(self, job_id: str) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE pending_jobs SET status = 'processing' WHERE id = ?",
                    (job_id,),
                )
                conn.commit()
            finally:
                conn.close()

    def has_pending_mbid(self, album_mbid: str) -> bool:
        """Check if a pending job already exists for this album MBID."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM pending_jobs WHERE album_mbid = ? AND status = 'pending' LIMIT 1",
                (album_mbid,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def get_pending(self) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM pending_jobs WHERE status = 'pending' ORDER BY created_at"
            ).fetchall()
        finally:
            conn.close()

    def get_all(self) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM pending_jobs ORDER BY created_at"
            ).fetchall()
        finally:
            conn.close()

    def reset_processing(self) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE pending_jobs SET status = 'pending' WHERE status = 'processing'"
                )
                conn.commit()
            finally:
                conn.close()

    def add_dead_letter(
        self,
        job_id: str,
        album_mbid: str,
        error_message: str,
        retry_count: int,
        max_retries: int,
    ) -> None:
        status = "exhausted" if retry_count >= max_retries else "pending"
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO dead_letters
                       (id, album_mbid, error_message, retry_count, max_retries, last_attempted_at, status)
                       VALUES (?, ?, ?, ?, ?, datetime('now'), ?)""",
                    (job_id, album_mbid, error_message, retry_count, max_retries, status),
                )
                conn.commit()
            finally:
                conn.close()

    def get_retryable_dead_letters(self) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM dead_letters WHERE status = 'pending' ORDER BY last_attempted_at"
            ).fetchall()
        finally:
            conn.close()

    def remove_dead_letter(self, job_id: str) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM dead_letters WHERE id = ?", (job_id,))
                conn.commit()
            finally:
                conn.close()

    def update_dead_letter_attempt(
        self, job_id: str, error_message: str, retry_count: int
    ) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    """UPDATE dead_letters
                       SET error_message = ?,
                           retry_count = ?,
                           last_attempted_at = datetime('now'),
                           status = CASE WHEN ? >= max_retries THEN 'exhausted' ELSE 'pending' END
                       WHERE id = ?""",
                    (error_message, retry_count, retry_count, job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get_dead_letter_count(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM dead_letters").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

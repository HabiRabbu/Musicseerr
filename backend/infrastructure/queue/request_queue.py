import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from infrastructure.queue.queue_store import QueueStore
    from infrastructure.persistence.request_history import RequestHistoryStore

logger = logging.getLogger(__name__)


class QueueInterface(ABC):
    @abstractmethod
    async def add(self, item: Any) -> Any:
        pass
    
    @abstractmethod
    async def start(self) -> None:
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        pass
    
    @abstractmethod
    def get_status(self) -> dict:
        pass


class QueuedRequest:
    __slots__ = ('album_mbid', 'future', 'job_id', 'retry_count', 'recovered', 'enqueued_at')
    
    def __init__(
        self,
        album_mbid: str,
        future: Optional[asyncio.Future] = None,
        job_id: str = "",
        recovered: bool = False,
    ):
        self.album_mbid = album_mbid
        self.future: asyncio.Future = future if future is not None else asyncio.get_event_loop().create_future()
        self.job_id = job_id or str(uuid.uuid4())
        self.retry_count = 0
        self.recovered = recovered
        self.enqueued_at = time.monotonic()


class RequestQueue(QueueInterface):
    def __init__(
        self,
        processor: Callable,
        maxsize: int = 200,
        store: "QueueStore | None" = None,
        max_retries: int = 3,
        request_history: "RequestHistoryStore | None" = None,
        concurrency: int = 2,
        on_import_callback: Callable | None = None,
    ):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._processor = processor
        self._worker_tasks: list[asyncio.Task] = []
        self._active_workers = 0
        self._maxsize = maxsize
        self._store = store
        self._max_retries = max_retries
        self._request_history = request_history
        self._concurrency = max(1, min(concurrency, 5))
        self._cancelled_mbids: set[str] = set()
        self._enqueue_lock = asyncio.Lock()
        self._recovered = False
        self._on_import_callback = on_import_callback
    
    async def add(self, album_mbid: str) -> dict:
        """Blocking enqueue that waits for the result."""
        await self.start()
        
        request = QueuedRequest(album_mbid)
        if self._store:
            self._store.enqueue(request.job_id, album_mbid)
        await self._queue.put(request)
        
        result = await request.future
        return result

    async def enqueue(self, album_mbid: str) -> bool:
        """Fire-and-forget enqueue. Returns True if enqueued, False if duplicate."""
        async with self._enqueue_lock:
            if self._store and self._store.has_active_mbid(album_mbid):
                return False

            # Clear any prior cancellation so re-requests aren't silently dropped
            self._cancelled_mbids.discard(album_mbid.lower())

            await self.start()
            request = QueuedRequest(album_mbid)
            if self._store:
                self._store.enqueue(request.job_id, album_mbid)
            await self._queue.put(request)
            return True

    async def cancel(self, album_mbid: str) -> bool:
        """Remove a pending job from the queue. Returns True if removed."""
        removed = False
        if self._store:
            removed = self._store.remove_by_mbid(album_mbid)
        # Mark for skip - items already in the asyncio.Queue can't be removed,
        # so workers check this set before processing.
        self._cancelled_mbids.add(album_mbid.lower())
        return removed

    async def start(self) -> None:
        alive = [t for t in self._worker_tasks if not t.done()]
        if len(alive) < self._concurrency:
            for _ in range(self._concurrency - len(alive)):
                task = asyncio.create_task(self._process_queue())
                self._worker_tasks.append(task)
            if not self._recovered:
                self._recovered = True
                self._recover_pending()
    
    async def stop(self) -> None:
        alive = [t for t in self._worker_tasks if not t.done()]
        if alive:
            await self.drain()
            for t in alive:
                t.cancel()
            await asyncio.gather(*alive, return_exceptions=True)
            self._worker_tasks.clear()
    
    async def drain(self, timeout: float = 30.0) -> None:
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            remaining = self._queue.qsize()
            logger.warning("Queue drain timeout: %d items remaining", remaining)
    
    def get_status(self) -> dict:
        status = {
            "queue_size": self._queue.qsize(),
            "max_size": self._maxsize,
            "processing": self._active_workers > 0,
            "active_workers": self._active_workers,
            "max_workers": self._concurrency,
        }
        if self._store:
            status["dead_letter_count"] = self._store.get_dead_letter_count()
            status["persisted_pending"] = len(self._store.get_all())
        return status
    
    def _recover_pending(self) -> None:
        if not self._store:
            return
        self._store.reset_processing()
        pending = self._store.get_pending()
        recovered = 0
        for row in pending:
            request = QueuedRequest(
                album_mbid=row["album_mbid"],
                job_id=row["id"],
                recovered=True,
            )
            try:
                self._queue.put_nowait(request)
                recovered += 1
                if self._request_history:
                    task = asyncio.ensure_future(self._backfill_history(row["album_mbid"]))
                    task.add_done_callback(
                        lambda t: t.exception() and logger.error("Backfill failed: %s", t.exception())
                        if not t.cancelled() and t.exception() else None
                    )
            except asyncio.QueueFull:
                logger.warning("Queue full during recovery, %d items deferred to next restart",
                               len(pending) - recovered)
                break
        self._retry_dead_letters()

    async def _backfill_history(self, album_mbid: str) -> None:
        """Create a minimal history record for recovered jobs that lack one."""
        if not self._request_history:
            return
        try:
            existing = await self._request_history.async_get_record(album_mbid)
            if not existing:
                await self._request_history.async_record_request(
                    musicbrainz_id=album_mbid,
                    artist_name="Unknown",
                    album_title="Unknown",
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to backfill history for %s: %s", album_mbid[:8], e)

    async def _update_history_on_result(self, album_mbid: str, result: dict) -> None:
        if not self._request_history:
            return
        try:
            from services.request_utils import extract_cover_url

            # Don't overwrite a user-initiated cancellation
            existing = await self._request_history.async_get_record(album_mbid)
            if existing and existing.status == "cancelled":
                return

            payload = result.get("payload", {})
            if not payload or not isinstance(payload, dict):
                await self._request_history.async_update_status(album_mbid, "downloading")
                return

            lidarr_album_id = payload.get("id")
            cover_url = extract_cover_url(payload)
            artist_mbid = None
            artist_data = payload.get("artist", {})
            if artist_data:
                artist_mbid = artist_data.get("foreignArtistId")

            statistics = payload.get("statistics", {})
            has_files = statistics.get("trackFileCount", 0) > 0

            # Persist metadata fields BEFORE status update / callback so the
            # record is complete when the import callback reads it.
            if lidarr_album_id:
                await self._request_history.async_update_lidarr_album_id(album_mbid, lidarr_album_id)
            if cover_url:
                await self._request_history.async_update_cover_url(album_mbid, cover_url)
            if artist_mbid:
                await self._request_history.async_update_artist_mbid(album_mbid, artist_mbid)

            if has_files:
                now_iso = datetime.now(timezone.utc).isoformat()
                await self._request_history.async_update_status(
                    album_mbid, "imported", completed_at=now_iso
                )
                # Invalidate caches so the album immediately appears as "In Library"
                if self._on_import_callback:
                    try:
                        enriched = await self._request_history.async_get_record(album_mbid)
                        if enriched:
                            await self._on_import_callback(enriched)
                    except Exception as cb_err:  # noqa: BLE001
                        logger.warning("Import callback failed for %s: %s", album_mbid[:8], cb_err)
            else:
                await self._request_history.async_update_status(album_mbid, "downloading")

        except Exception as e:  # noqa: BLE001
            logger.error("Failed to update history after processing %s: %s", album_mbid[:8], e)

    async def _update_history_on_failure(self, album_mbid: str, error: Exception) -> None:
        if not self._request_history:
            return
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            await self._request_history.async_update_status(
                album_mbid, "failed", completed_at=now_iso
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to update history on failure for %s: %s", album_mbid[:8], e)

    def _retry_dead_letters(self) -> None:
        if not self._store:
            return
        retryable = self._store.get_retryable_dead_letters()
        enqueued = 0
        for row in retryable:
            if self._store.has_pending_mbid(row["album_mbid"]):
                self._store.remove_dead_letter(row["id"])
                continue
            request = QueuedRequest(
                album_mbid=row["album_mbid"],
                job_id=row["id"],
                recovered=True,
            )
            request.retry_count = row["retry_count"]
            try:
                self._queue.put_nowait(request)
            except asyncio.QueueFull:
                logger.warning("Queue full during dead-letter retry, remaining deferred")
                break
            # Only remove dead letter + persist to pending AFTER successful in-memory enqueue
            self._store.remove_dead_letter(row["id"])
            self._store.enqueue(row["id"], row["album_mbid"])
            enqueued += 1

    async def _process_queue(self) -> None:
        while True:
            try:
                request: QueuedRequest = await self._queue.get()

                # Skip items cancelled while sitting in the asyncio.Queue
                if request.album_mbid.lower() in self._cancelled_mbids:
                    self._cancelled_mbids.discard(request.album_mbid.lower())
                    if not request.future.done():
                        request.future.cancel()
                    self._queue.task_done()
                    continue

                # Prevent unbounded growth from orphaned cancel entries
                if len(self._cancelled_mbids) > 200:
                    self._cancelled_mbids.clear()

                self._active_workers += 1
                if self._store:
                    self._store.mark_processing(request.job_id)

                try:
                    result = await self._processor(request.album_mbid)
                    if not request.future.done():
                        request.future.set_result(result)
                    if self._store:
                        self._store.dequeue(request.job_id)
                    await self._update_history_on_result(request.album_mbid, result)
                except Exception as e:  # noqa: BLE001
                    logger.error("Error processing request for %s (attempt %d/%d): %s",
                                 request.album_mbid[:8], request.retry_count + 1, self._max_retries, e)
                    if not request.future.done():
                        request.future.set_exception(e)
                    if self._store:
                        self._store.dequeue(request.job_id)
                        self._store.add_dead_letter(
                            job_id=request.job_id,
                            album_mbid=request.album_mbid,
                            error_message=str(e),
                            retry_count=request.retry_count + 1,
                            max_retries=self._max_retries,
                        )
                    await self._update_history_on_failure(request.album_mbid, e)
                finally:
                    self._active_workers -= 1
                    self._queue.task_done()
            
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                logger.error("Queue worker error: %s", e)

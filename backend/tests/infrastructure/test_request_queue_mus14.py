"""Tests for MUS-14 queue changes: dedup, cancel, concurrency, atomic enqueue."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from infrastructure.queue.queue_store import QueueStore
from infrastructure.queue.request_queue import RequestQueue


@pytest.fixture
def store(tmp_path: Path) -> QueueStore:
    return QueueStore(db_path=tmp_path / "test_queue.db")


@pytest.mark.asyncio
async def test_enqueue_dedup_rejects_duplicate(store: QueueStore):
    """Duplicate MBIDs are rejected by enqueue()."""
    processed = []

    async def processor(mbid: str) -> dict:
        await asyncio.sleep(10)
        processed.append(mbid)
        return {"status": "ok"}

    q = RequestQueue(processor=processor, store=store)
    first = await q.enqueue("mbid-aaa")
    second = await q.enqueue("mbid-aaa")

    assert first is True
    assert second is False
    await q.stop()


@pytest.mark.asyncio
async def test_enqueue_dedup_is_atomic(store: QueueStore):
    """Concurrent enqueue calls for the same MBID should only succeed once."""
    processed = []

    async def slow_processor(mbid: str) -> dict:
        await asyncio.sleep(10)
        processed.append(mbid)
        return {"status": "ok"}

    q = RequestQueue(processor=slow_processor, store=store)
    results = await asyncio.gather(
        q.enqueue("mbid-race"),
        q.enqueue("mbid-race"),
        q.enqueue("mbid-race"),
    )

    assert sum(results) == 1
    await q.stop()


@pytest.mark.asyncio
async def test_cancel_skips_queued_item(store: QueueStore):
    """Cancelled items are skipped by the worker."""
    processed = []
    gate = asyncio.Event()

    async def gated_processor(mbid: str) -> dict:
        await gate.wait()
        processed.append(mbid)
        return {"status": "ok"}

    q = RequestQueue(processor=gated_processor, store=store, concurrency=1)
    await q.enqueue("mbid-first")
    await q.enqueue("mbid-second")

    await q.cancel("mbid-second")
    gate.set()
    await asyncio.sleep(0.5)

    assert "mbid-first" in processed
    assert "mbid-second" not in processed
    await q.stop()


@pytest.mark.asyncio
async def test_concurrent_workers_process_in_parallel(store: QueueStore):
    """Multiple workers process items concurrently."""
    active = {"count": 0, "max": 0}
    lock = asyncio.Lock()

    async def tracking_processor(mbid: str) -> dict:
        async with lock:
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
        await asyncio.sleep(0.2)
        async with lock:
            active["count"] -= 1
        return {"status": "ok"}

    q = RequestQueue(processor=tracking_processor, store=store, concurrency=3)

    await q.enqueue("mbid-a")
    await q.enqueue("mbid-b")
    await q.enqueue("mbid-c")

    await asyncio.sleep(0.5)

    assert active["max"] >= 2
    await q.stop()


@pytest.mark.asyncio
async def test_store_persisted_before_memory_queue():
    """enqueue() persists to store before putting in asyncio.Queue."""
    call_order: list[str] = []

    class TrackedStore:
        def has_active_mbid(self, mbid: str) -> bool:
            return False

        def enqueue(self, job_id: str, mbid: str) -> bool:
            call_order.append("store_enqueue")
            return True

        def get_dead_letter_count(self) -> int:
            return 0

        def get_all(self) -> list:
            return []

        def reset_processing(self) -> None:
            pass

        def get_pending(self) -> list:
            return []

        def get_retryable_dead_letters(self) -> list:
            return []

        def mark_processing(self, job_id: str) -> None:
            pass

        def dequeue(self, job_id: str) -> None:
            pass

    original_put = asyncio.Queue.put

    async def tracked_put(self, item):
        call_order.append("queue_put")
        return await original_put(self, item)

    asyncio.Queue.put = tracked_put
    try:
        async def noop_processor(mbid: str) -> dict:
            return {"status": "ok"}

        q = RequestQueue(processor=noop_processor, store=TrackedStore())
        await q.enqueue("mbid-order-test")

        assert call_order.index("store_enqueue") < call_order.index("queue_put")
        await q.stop()
    finally:
        asyncio.Queue.put = original_put


@pytest.mark.asyncio
async def test_cancel_then_re_request_processes_new_request(store: QueueStore):
    """A cancelled MBID can be re-requested and will be processed."""
    processed = []
    gate = asyncio.Event()

    async def gated_processor(mbid: str) -> dict:
        await gate.wait()
        processed.append(mbid)
        return {"status": "ok"}

    q = RequestQueue(processor=gated_processor, store=store, concurrency=1)

    # Enqueue, cancel, then re-enqueue the same MBID
    first = await q.enqueue("mbid-bounce")
    assert first is True
    await q.cancel("mbid-bounce")
    second = await q.enqueue("mbid-bounce")
    assert second is True

    gate.set()
    await asyncio.sleep(0.5)

    # The re-request should have been processed (not skipped by stale cancel)
    assert "mbid-bounce" in processed
    await q.stop()


@pytest.mark.asyncio
async def test_cancelled_mbids_bounded(store: QueueStore):
    """_cancelled_mbids set doesn't grow unbounded."""
    async def noop(mbid: str) -> dict:
        return {"status": "ok"}

    q = RequestQueue(processor=noop, store=store, concurrency=1)

    # Cancel 250 non-existent MBIDs (orphan cancels)
    for i in range(250):
        await q.cancel(f"orphan-{i}")

    assert len(q._cancelled_mbids) == 250

    # Process one item — triggers the cleanup threshold
    await q.enqueue("mbid-trigger")
    await asyncio.sleep(0.5)

    assert len(q._cancelled_mbids) <= 200
    await q.stop()

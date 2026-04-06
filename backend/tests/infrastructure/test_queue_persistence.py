import asyncio
import pytest
from pathlib import Path
from infrastructure.queue.queue_store import QueueStore
from infrastructure.queue.request_queue import RequestQueue


@pytest.fixture
def store(tmp_path: Path) -> QueueStore:
    return QueueStore(db_path=tmp_path / "test_queue.db")


@pytest.mark.asyncio
async def test_jobs_survive_restart(store: QueueStore):
    processed = []

    async def slow_processor(mbid: str) -> dict:
        await asyncio.sleep(100)
        processed.append(mbid)
        return {"status": "ok"}

    q1 = RequestQueue(processor=slow_processor, store=store)
    await q1.start()

    store.enqueue("job-1", "mbid-abc")
    store.mark_processing("job-1")

    for task in q1._worker_tasks:
        task.cancel()
    for task in q1._worker_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    q1._worker_tasks.clear()

    fast_processed = []

    async def fast_processor(mbid: str) -> dict:
        fast_processed.append(mbid)
        return {"status": "ok"}

    q2 = RequestQueue(processor=fast_processor, store=store)
    await q2.start()

    await asyncio.sleep(0.5)
    assert "mbid-abc" in fast_processed
    await q2.stop()


@pytest.mark.asyncio
async def test_failed_job_lands_in_dead_letter(store: QueueStore):
    async def failing_processor(mbid: str) -> dict:
        raise ValueError("Lidarr is down")

    q = RequestQueue(processor=failing_processor, store=store)
    await q.start()

    try:
        await asyncio.wait_for(q.add("mbid-fail"), timeout=2.0)
    except (ValueError, asyncio.TimeoutError):
        pass

    await asyncio.sleep(0.1)
    assert store.get_dead_letter_count() >= 1
    await q.stop()


@pytest.mark.asyncio
async def test_dead_letter_retry_on_restart(store: QueueStore):
    store.add_dead_letter("dlj-1", "mbid-retry", "old error", retry_count=1, max_retries=3)

    processed = []

    async def processor(mbid: str) -> dict:
        processed.append(mbid)
        return {"status": "ok"}

    q = RequestQueue(processor=processor, store=store)
    await q.start()
    await asyncio.sleep(0.5)
    assert "mbid-retry" in processed
    await q.stop()


@pytest.mark.asyncio
async def test_successful_job_removed_from_store(store: QueueStore):
    async def ok_processor(mbid: str) -> dict:
        return {"status": "ok"}

    q = RequestQueue(processor=ok_processor, store=store)
    await q.start()

    await asyncio.wait_for(q.add("mbid-ok"), timeout=2.0)
    assert len(store.get_all()) == 0
    await q.stop()


@pytest.mark.asyncio
async def test_exhausted_dead_letter_not_retried(store: QueueStore):
    store.add_dead_letter("dlj-ex", "mbid-exhausted", "fatal", retry_count=3, max_retries=3)

    processed = []

    async def processor(mbid: str) -> dict:
        processed.append(mbid)
        return {"status": "ok"}

    q = RequestQueue(processor=processor, store=store)
    await q.start()
    await asyncio.sleep(0.3)
    assert "mbid-exhausted" not in processed
    await q.stop()

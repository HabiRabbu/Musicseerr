import asyncio
import logging
import time
from enum import Enum
from typing import Any

import msgspec

from api.v1.schemas.discover import (
    DiscoverQueueEnrichment,
    DiscoverQueueItemFull,
    DiscoverQueueResponse,
    DiscoverQueueStatusResponse,
    QueueGenerateResponse,
)
from infrastructure.serialization import clone_with_updates
from services.discover_service import DiscoverService
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)


class QueueBuildStatus(str, Enum):
    IDLE = "idle"
    BUILDING = "building"
    READY = "ready"
    ERROR = "error"


class SourceQueueState:
    __slots__ = ("status", "queue", "error", "built_at", "task")

    def __init__(self) -> None:
        self.status: QueueBuildStatus = QueueBuildStatus.IDLE
        self.queue: DiscoverQueueResponse | None = None
        self.error: str | None = None
        self.built_at: float = 0.0
        self.task: asyncio.Task[None] | None = None


class DiscoverQueueManager:
    def __init__(
        self,
        discover_service: DiscoverService,
        preferences_service: PreferencesService,
    ) -> None:
        self._discover = discover_service
        self._preferences = preferences_service
        self._states: dict[str, SourceQueueState] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, source: str) -> SourceQueueState:
        if source not in self._states:
            self._states[source] = SourceQueueState()
        return self._states[source]

    def _get_ttl(self) -> int:
        adv = self._preferences.get_advanced_settings()
        return adv.discover_queue_ttl

    def _is_stale(self, state: SourceQueueState) -> bool:
        if state.status != QueueBuildStatus.READY or state.queue is None:
            return True
        return (time.time() - state.built_at) > self._get_ttl()

    def get_status(self, source: str) -> DiscoverQueueStatusResponse:
        state = self._get_state(source)
        if state.status == QueueBuildStatus.READY and state.queue:
            return DiscoverQueueStatusResponse(
                status=state.status.value,
                source=source,
                queue_id=state.queue.queue_id,
                item_count=len(state.queue.items),
                built_at=state.built_at,
                stale=self._is_stale(state),
            )
        if state.status == QueueBuildStatus.ERROR:
            return DiscoverQueueStatusResponse(
                status=state.status.value,
                source=source,
                error=state.error,
            )
        return DiscoverQueueStatusResponse(status=state.status.value, source=source)

    @staticmethod
    def _build_generate_response(action: str, status: DiscoverQueueStatusResponse) -> QueueGenerateResponse:
        return QueueGenerateResponse(
            action=action,
            status=status.status,
            source=status.source,
            queue_id=status.queue_id,
            item_count=status.item_count,
            built_at=status.built_at,
            stale=status.stale,
            error=status.error,
        )

    def get_queue(self, source: str) -> DiscoverQueueResponse | None:
        state = self._get_state(source)
        if state.status == QueueBuildStatus.READY and state.queue and not self._is_stale(state):
            return state.queue
        return None

    async def start_build(self, source: str, *, force: bool = False) -> QueueGenerateResponse:
        async with self._lock:
            state = self._get_state(source)

            if state.status == QueueBuildStatus.BUILDING:
                return self._build_generate_response("already_building", self.get_status(source))

            if not force and state.status == QueueBuildStatus.READY and not self._is_stale(state):
                return self._build_generate_response("already_ready", self.get_status(source))

            if state.task and not state.task.done():
                state.task.cancel()

            state.status = QueueBuildStatus.BUILDING
            state.error = None
            state.task = asyncio.create_task(self._do_build(source))

        return self._build_generate_response("started", self.get_status(source))

    async def build_hydrated_queue(self, source: str, count: int | None = None) -> DiscoverQueueResponse:
        queue = await self._discover.build_queue(count=count, source=source)
        return await self._hydrate_queue_items(queue, source)

    async def _hydrate_queue_items(
        self, queue: DiscoverQueueResponse, source: str
    ) -> DiscoverQueueResponse:
        if not queue.items:
            return queue

        concurrency = min(4, len(queue.items))
        semaphore = asyncio.Semaphore(concurrency)

        async def hydrate_item(item: Any) -> Any:
            if getattr(item, "enrichment", None) is not None:
                return item
            try:
                async with semaphore:
                    enrichment = await self._discover.enrich_queue_item(item.release_group_mbid)
            except Exception as exc:
                logger.warning(
                    "Queue item enrichment failed (source=%s, release_group_mbid=%s): %s",
                    source,
                    item.release_group_mbid,
                    exc,
                )
                enrichment = DiscoverQueueEnrichment()

            item_data = msgspec.to_builtins(item)
            item_data["enrichment"] = enrichment
            return DiscoverQueueItemFull(**item_data)

        hydrated_items = await asyncio.gather(*(hydrate_item(item) for item in queue.items))
        return clone_with_updates(queue, {"items": hydrated_items})

    async def _do_build(self, source: str) -> None:
        state = self._get_state(source)
        try:
            logger.info("Background queue build started (source=%s)", source)
            queue = await self.build_hydrated_queue(source)
            state.queue = queue
            state.built_at = time.time()
            state.status = QueueBuildStatus.READY
            logger.info(
                "Background queue build complete (source=%s, items=%d, queue_id=%s)",
                source,
                len(queue.items),
                queue.queue_id,
            )
        except asyncio.CancelledError:
            logger.info("Background queue build cancelled (source=%s)", source)
            if state.status == QueueBuildStatus.BUILDING:
                state.status = QueueBuildStatus.IDLE
            raise
        except Exception as e:
            logger.error("Background queue build failed (source=%s): %s", source, e)
            state.status = QueueBuildStatus.ERROR
            state.error = str(e)

    async def consume_queue(self, source: str) -> DiscoverQueueResponse | None:
        state = self._get_state(source)
        if state.status != QueueBuildStatus.READY or state.queue is None:
            return None
        if self._is_stale(state):
            logger.info("Discarding stale pre-built queue (source=%s)", source)
            state.queue = None
            state.status = QueueBuildStatus.IDLE
            state.built_at = 0.0
            return None
        queue = state.queue
        state.queue = None
        state.status = QueueBuildStatus.IDLE
        state.built_at = 0.0
        return queue

    def invalidate(self, source: str | None = None) -> None:
        if source:
            state = self._get_state(source)
            if state.task and not state.task.done():
                state.task.cancel()
            self._states[source] = SourceQueueState()
        else:
            for src in list(self._states.keys()):
                self.invalidate(src)

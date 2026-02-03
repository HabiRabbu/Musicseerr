import asyncio
import json
import logging
import threading
import time
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict

if TYPE_CHECKING:
    from infrastructure.cache.persistent_cache import LibraryCache

logger = logging.getLogger(__name__)


@dataclass
class CacheSyncProgress:
    is_syncing: bool
    phase: Optional[str]
    total_items: int
    processed_items: int
    current_item: Optional[str]
    started_at: Optional[float]
    error_message: Optional[str] = None
    total_artists: int = 0
    processed_artists: int = 0
    total_albums: int = 0
    processed_albums: int = 0

    @property
    def progress_percent(self) -> int:
        if self.total_items == 0:
            return 100
        return int((self.processed_items / self.total_items) * 100)


class CacheStatusService:

    _instance: Optional['CacheStatusService'] = None
    _creation_lock = threading.Lock()

    def __new__(cls, library_cache: Optional['LibraryCache'] = None):
        with cls._creation_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize(library_cache)
            elif library_cache is not None and cls._instance._library_cache is None:
                cls._instance._library_cache = library_cache
        return cls._instance

    def _initialize(self, library_cache: Optional['LibraryCache'] = None):
        self._library_cache = library_cache
        self._progress = CacheSyncProgress(
            is_syncing=False,
            phase=None,
            total_items=0,
            processed_items=0,
            current_item=None,
            started_at=None,
            error_message=None,
            total_artists=0,
            processed_artists=0,
            total_albums=0,
            processed_albums=0
        )
        self._cancel_event = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None
        self._state_lock = asyncio.Lock()
        self._sse_subscribers: set[asyncio.Queue] = set()
        self._sse_lock = threading.Lock()

    def set_library_cache(self, library_cache: 'LibraryCache'):
        self._library_cache = library_cache

    def subscribe_sse(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._sse_lock:
            self._sse_subscribers.add(queue)
        return queue

    def unsubscribe_sse(self, queue: asyncio.Queue) -> None:
        with self._sse_lock:
            self._sse_subscribers.discard(queue)

    async def broadcast_progress(self) -> None:
        progress = self.get_progress()
        data = json.dumps({
            'is_syncing': progress.is_syncing,
            'phase': progress.phase,
            'total_items': progress.total_items,
            'processed_items': progress.processed_items,
            'progress_percent': progress.progress_percent,
            'current_item': progress.current_item,
            'started_at': progress.started_at,
            'error_message': progress.error_message,
            'total_artists': progress.total_artists,
            'processed_artists': progress.processed_artists,
            'total_albums': progress.total_albums,
            'processed_albums': progress.processed_albums
        })
        with self._sse_lock:
            dead_queues = []
            for queue in self._sse_subscribers:
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    dead_queues.append(queue)
            for q in dead_queues:
                self._sse_subscribers.discard(q)

    async def start_sync(self, phase: str, total_items: int, total_artists: int = 0, total_albums: int = 0):
        async with self._state_lock:
            self._cancel_event.clear()
            started_at = time.time()
            self._progress = CacheSyncProgress(
                is_syncing=True,
                phase=phase,
                total_items=total_items,
                processed_items=0,
                current_item=None,
                started_at=started_at,
                error_message=None,
                total_artists=total_artists,
                processed_artists=0,
                total_albums=total_albums,
                processed_albums=0
            )
            logger.info(f"Cache sync started: {phase} ({total_items} items)")

            if self._library_cache:
                try:
                    await self._library_cache.save_sync_state(
                        status='running',
                        phase=phase,
                        total_artists=total_artists,
                        total_albums=total_albums,
                        started_at=started_at
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist sync state: {e}")

        await self.broadcast_progress()

    async def update_progress(
        self,
        processed: int,
        current_item: Optional[str] = None,
        processed_artists: Optional[int] = None,
        processed_albums: Optional[int] = None
    ):
        async with self._state_lock:
            if processed >= self._progress.processed_items:
                self._progress.processed_items = processed
                self._progress.current_item = current_item
                if processed_artists is not None:
                    self._progress.processed_artists = processed_artists
                if processed_albums is not None:
                    self._progress.processed_albums = processed_albums

        await self.broadcast_progress()

    async def update_phase(self, phase: str, total_items: int):
        async with self._state_lock:
            self._progress.phase = phase
            self._progress.total_items = total_items
            self._progress.processed_items = 0
            self._progress.current_item = None

            if self._library_cache:
                try:
                    await self._library_cache.save_sync_state(
                        status='running',
                        phase=phase,
                        total_artists=self._progress.total_artists,
                        processed_artists=self._progress.processed_artists,
                        total_albums=self._progress.total_albums if phase == 'albums' else total_items,
                        processed_albums=self._progress.processed_albums,
                        started_at=self._progress.started_at
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist phase update: {e}")

        await self.broadcast_progress()

    async def persist_progress(self):
        if self._library_cache:
            try:
                await self._library_cache.save_sync_state(
                    status='running',
                    phase=self._progress.phase,
                    total_artists=self._progress.total_artists,
                    processed_artists=self._progress.processed_artists,
                    total_albums=self._progress.total_albums,
                    processed_albums=self._progress.processed_albums,
                    current_item=self._progress.current_item,
                    started_at=self._progress.started_at
                )
            except Exception as e:
                logger.warning(f"Failed to persist progress: {e}")

    async def complete_sync(self, error_message: Optional[str] = None):
        async with self._state_lock:
            status = 'failed' if error_message else 'completed'
            logger.info(f"Cache sync {status}: {self._progress.phase}")

            if self._library_cache:
                try:
                    await self._library_cache.save_sync_state(
                        status=status,
                        phase=self._progress.phase,
                        total_artists=self._progress.total_artists,
                        processed_artists=self._progress.processed_artists,
                        total_albums=self._progress.total_albums,
                        processed_albums=self._progress.processed_albums,
                        error_message=error_message,
                        started_at=self._progress.started_at
                    )
                    await self._library_cache.clear_sync_state()
                except Exception as e:
                    logger.warning(f"Failed to persist completion: {e}")

            self._progress = CacheSyncProgress(
                is_syncing=False,
                phase=None,
                total_items=0,
                processed_items=0,
                current_item=None,
                started_at=None,
                error_message=error_message,
                total_artists=0,
                processed_artists=0,
                total_albums=0,
                processed_albums=0
            )

        await self.broadcast_progress()

    def get_progress(self) -> CacheSyncProgress:
        return self._progress

    def is_syncing(self) -> bool:
        return self._progress.is_syncing

    async def cancel_current_sync(self):
        async with self._state_lock:
            if self._progress.is_syncing:
                logger.warning(f"Cancelling in-progress sync: phase={self._progress.phase}, progress={self._progress.processed_items}/{self._progress.total_items}")
                self._cancel_event.set()

                if self._library_cache:
                    try:
                        await self._library_cache.save_sync_state(
                            status='cancelled',
                            phase=self._progress.phase,
                            total_artists=self._progress.total_artists,
                            processed_artists=self._progress.processed_artists,
                            total_albums=self._progress.total_albums,
                            processed_albums=self._progress.processed_albums,
                            started_at=self._progress.started_at
                        )
                    except Exception as e:
                        logger.warning(f"Failed to persist cancellation: {e}")

                self._progress = CacheSyncProgress(
                    is_syncing=False,
                    phase=None,
                    total_items=0,
                    processed_items=0,
                    current_item=None,
                    started_at=None,
                    error_message=None,
                    total_artists=0,
                    processed_artists=0,
                    total_albums=0,
                    processed_albums=0
                )

        await self.broadcast_progress()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def set_current_task(self, task: Optional[asyncio.Task]):
        self._current_task = task

    async def wait_for_completion(self):
        if self._current_task and not self._current_task.done():
            try:
                await asyncio.wait_for(self._current_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Sync task did not complete within timeout, forcing cancellation")
                self._current_task.cancel()
            except Exception as e:
                logger.error(f"Error waiting for sync completion: {e}")

    def can_start_sync(self) -> bool:
        return not self._progress.is_syncing

    async def restore_from_persistence(self) -> Optional[dict]:
        if not self._library_cache:
            return None

        try:
            state = await self._library_cache.get_sync_state()
            if state and state.get('status') == 'running':
                logger.info(f"Found interrupted sync: phase={state.get('phase')}, "
                           f"artists={state.get('processed_artists')}/{state.get('total_artists')}, "
                           f"albums={state.get('processed_albums')}/{state.get('total_albums')}")

                self._progress = CacheSyncProgress(
                    is_syncing=True,
                    phase=state.get('phase'),
                    total_items=state.get('total_albums') if state.get('phase') == 'albums' else state.get('total_artists'),
                    processed_items=state.get('processed_albums') if state.get('phase') == 'albums' else state.get('processed_artists'),
                    current_item=state.get('current_item'),
                    started_at=state.get('started_at'),
                    error_message=None,
                    total_artists=state.get('total_artists', 0),
                    processed_artists=state.get('processed_artists', 0),
                    total_albums=state.get('total_albums', 0),
                    processed_albums=state.get('processed_albums', 0)
                )
                return state
            return None
        except Exception as e:
            logger.error(f"Failed to restore from persistence: {e}")
            return None

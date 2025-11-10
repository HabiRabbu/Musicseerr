import asyncio
import logging
import threading
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheSyncProgress:
    is_syncing: bool
    phase: Optional[str]
    total_items: int
    processed_items: int
    current_item: Optional[str]
    started_at: Optional[float]
    
    @property
    def progress_percent(self) -> int:
        if self.total_items == 0:
            return 100
        return int((self.processed_items / self.total_items) * 100)


class CacheStatusService:
    
    _instance: Optional['CacheStatusService'] = None
    _creation_lock = threading.Lock()
    
    def __new__(cls):
        with cls._creation_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._progress = CacheSyncProgress(
            is_syncing=False,
            phase=None,
            total_items=0,
            processed_items=0,
            current_item=None,
            started_at=None
        )
        self._cancel_event = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None
        self._state_lock = asyncio.Lock()
    
    async def start_sync(self, phase: str, total_items: int):
        import time
        async with self._state_lock:
            self._cancel_event.clear()
            self._progress = CacheSyncProgress(
                is_syncing=True,
                phase=phase,
                total_items=total_items,
                processed_items=0,
                current_item=None,
                started_at=time.time()
            )
            logger.info(f"Cache sync started: {phase} ({total_items} items)")
    
    async def update_progress(self, processed: int, current_item: Optional[str] = None):
        async with self._state_lock:
            self._progress.processed_items = processed
            self._progress.current_item = current_item
    
    async def complete_sync(self):
        async with self._state_lock:
            logger.info(f"Cache sync completed: {self._progress.phase}")
            self._progress = CacheSyncProgress(
                is_syncing=False,
                phase=None,
                total_items=0,
                processed_items=0,
                current_item=None,
                started_at=None
            )
    
    def get_progress(self) -> CacheSyncProgress:
        return self._progress
    
    def is_syncing(self) -> bool:
        return self._progress.is_syncing
    
    async def cancel_current_sync(self):
        async with self._state_lock:
            if self._progress.is_syncing:
                logger.warning(f"Cancelling in-progress sync: phase={self._progress.phase}, progress={self._progress.processed_items}/{self._progress.total_items}")
                self._cancel_event.set()
                self._progress = CacheSyncProgress(
                    is_syncing=False,
                    phase=None,
                    total_items=0,
                    processed_items=0,
                    current_item=None,
                    started_at=None
                )
    
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


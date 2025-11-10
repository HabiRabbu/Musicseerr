import asyncio
import logging
from typing import Any, Callable, Optional
from abc import ABC, abstractmethod

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
    __slots__ = ('album_mbid', 'future')
    
    def __init__(self, album_mbid: str):
        self.album_mbid = album_mbid
        self.future: asyncio.Future = asyncio.Future()


class RequestQueue(QueueInterface):
    def __init__(self, processor: Callable, maxsize: int = 200):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._processor = processor
        self._processor_task: Optional[asyncio.Task] = None
        self._processing = False
        self._maxsize = maxsize
    
    async def add(self, album_mbid: str) -> dict:
        await self.start()
        
        request = QueuedRequest(album_mbid)
        await self._queue.put(request)
        
        result = await request.future
        return result
    
    async def start(self) -> None:
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_queue())
            logger.info("Queue processor started")
    
    async def stop(self) -> None:
        if self._processor_task and not self._processor_task.done():
            await self.drain()
            
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
            logger.info("Queue processor stopped")
    
    async def drain(self, timeout: float = 30.0) -> None:
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
            logger.info("Queue drained successfully")
        except asyncio.TimeoutError:
            remaining = self._queue.qsize()
            logger.warning(f"Queue drain timeout: {remaining} items remaining")
    
    def get_status(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "max_size": self._maxsize,
            "processing": self._processing,
        }
    
    async def _process_queue(self) -> None:
        while True:
            try:
                request: QueuedRequest = await self._queue.get()
                self._processing = True
                
                try:
                    result = await self._processor(request.album_mbid)
                    request.future.set_result(result)
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    request.future.set_exception(e)
                finally:
                    self._queue.task_done()
                    self._processing = False
            
            except asyncio.CancelledError:
                logger.info("Queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
                self._processing = False

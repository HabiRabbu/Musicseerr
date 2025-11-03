"""Request queue for managing album add operations."""
import asyncio
import logging
from typing import Optional

from utils import lidarr
from utils.common import ApiError

logger = logging.getLogger(__name__)

_queue: Optional[asyncio.Queue] = None
_processor_task: Optional[asyncio.Task] = None
_processing = False


class QueuedRequest:
    """A queued album request with a future for the result."""
    
    __slots__ = ('album_mbid', 'future')
    
    def __init__(self, album_mbid: str):
        self.album_mbid = album_mbid
        self.future: asyncio.Future = asyncio.Future()


def _get_queue() -> asyncio.Queue:
    """Get or create the request queue."""
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def _process_queue() -> None:
    """Background task to process queued requests."""
    global _processing
    queue = _get_queue()
    
    while True:
        try:
            request: QueuedRequest = await queue.get()
            _processing = True
            
            try:
                result = await lidarr.add_album(request.album_mbid)
                request.future.set_result(result)
            except ApiError as e:
                request.future.set_exception(e)
            except Exception as e:
                logger.error(f"Unexpected error processing request: {e}")
                request.future.set_exception(
                    ApiError("Request processing failed", str(e))
                )
            finally:
                queue.task_done()
                _processing = False
        
        except asyncio.CancelledError:
            logger.info("Queue processor cancelled")
            break
        except Exception as e:
            logger.error(f"Queue processor error: {e}")
            _processing = False


def start_processor() -> None:
    """Start the queue processor if not already running."""
    global _processor_task
    if _processor_task is None or _processor_task.done():
        _processor_task = asyncio.create_task(_process_queue())
        logger.info("Queue processor started")


async def stop_processor() -> None:
    """Stop the queue processor gracefully."""
    global _processor_task
    if _processor_task and not _processor_task.done():
        _processor_task.cancel()
        try:
            await _processor_task
        except asyncio.CancelledError:
            pass
        _processor_task = None
        logger.info("Queue processor stopped")


async def add_to_queue(album_mbid: str) -> dict:
    """Add an album request to the queue and wait for result.
    
    Args:
        album_mbid: MusicBrainz release group ID
    
    Returns:
        Result dict from lidarr.add_album()
    
    Raises:
        ApiError: If the request fails
    """
    start_processor()
    
    request = QueuedRequest(album_mbid)
    queue = _get_queue()
    await queue.put(request)
    
    # Wait for result
    result = await request.future
    return result


def get_queue_status() -> dict:
    """Get current queue status.
    
    Returns:
        Dict with queue_size and processing status
    """
    queue = _get_queue()
    return {
        "queue_size": queue.qsize(),
        "processing": _processing,
    }

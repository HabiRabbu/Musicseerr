import asyncio
from typing import Optional
from utils import lidarr
from utils.common import ApiError

_queue: Optional[asyncio.Queue] = None
_processor_task: Optional[asyncio.Task] = None
_processing = False


class QueuedRequest:
    def __init__(self, album_mbid: str):
        self.album_mbid = album_mbid
        self.future: asyncio.Future = asyncio.Future()


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def _process_queue():
    global _processing
    queue = get_queue()
    
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
                request.future.set_exception(
                    ApiError("Request processing failed", str(e))
                )
            finally:
                queue.task_done()
                _processing = False
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Queue processor error: {e}")
            _processing = False


def start_processor():
    global _processor_task
    if _processor_task is None or _processor_task.done():
        _processor_task = asyncio.create_task(_process_queue())


async def stop_processor():
    global _processor_task
    if _processor_task and not _processor_task.done():
        _processor_task.cancel()
        try:
            await _processor_task
        except asyncio.CancelledError:
            pass
        _processor_task = None


async def add_to_queue(album_mbid: str) -> dict:
    start_processor()
    
    request = QueuedRequest(album_mbid)
    queue = get_queue()
    await queue.put(request)
    
    result = await request.future
    return result


def get_queue_status() -> dict:
    queue = get_queue()
    return {
        "queue_size": queue.qsize(),
        "processing": _processing,
    }

import asyncio
import logging
from typing import TypeVar, Awaitable, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RequestDeduplicator:
    """
    Prevents duplicate concurrent requests by coalescing identical requests.
    
    If request A is in-flight and request B arrives with the same key,
    request B will wait for A's result instead of making a duplicate call.
    """
    
    def __init__(self):
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()
    
    async def dedupe(
        self,
        key: str,
        coro_factory: Callable[[], Awaitable[T]]
    ) -> T:
        async with self._lock:
            if key in self._pending:
                logger.debug(f"Deduplicating request: {key}")
                future = self._pending[key]
                should_execute = False
            else:
                future = asyncio.get_event_loop().create_future()
                self._pending[key] = future
                should_execute = True
        
        if should_execute:
            try:
                result = await coro_factory()
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                async with self._lock:
                    self._pending.pop(key, None)
        
        return await future


_global_deduplicator = RequestDeduplicator()


def get_deduplicator() -> RequestDeduplicator:
    return _global_deduplicator


def deduplicate(key_func: Callable[..., str]):
    """
    Decorator that deduplicates concurrent calls to the same function
    with the same key.
    
    Usage:
        @deduplicate(lambda self, artist_id: f"artist:{artist_id}")
        async def get_artist(self, artist_id: str) -> Artist:
            ...
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            key = key_func(*args, **kwargs)
            dedup = get_deduplicator()
            return await dedup.dedupe(key, lambda: func(*args, **kwargs))
        return wrapper
    return decorator

import asyncio
import logging
from typing import Callable, Any
from functools import wraps
from infrastructure.cache.memory_cache import CacheInterface

logger = logging.getLogger(__name__)


def _handle_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Background cache task failed: {exc}")


def make_cache_key(*args, **kwargs) -> str:
    parts = [str(arg) for arg in args]
    if kwargs:
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(parts)


def cached(
    cache: CacheInterface,
    ttl_seconds: int | Callable[[Any], int] = 60,
    key_prefix: str = "",
    cache_none: bool = False
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{make_cache_key(*args, **kwargs)}"

            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)

            if result is not None or cache_none:
                actual_ttl = ttl_seconds(result) if callable(ttl_seconds) else ttl_seconds
                task = asyncio.create_task(cache.set(cache_key, result, actual_ttl))
                task.add_done_callback(_handle_task_exception)

            return result

        return wrapper
    return decorator


def cached_method(
    key_fn: Callable[..., str],
    ttl_seconds: int | Callable[[Any], int] = 300,
    cache_none: bool = False
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            cache_key = key_fn(*args, **kwargs)
            cached_value = await self._cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            result = await func(self, *args, **kwargs)

            if result is not None or cache_none:
                actual_ttl = ttl_seconds(result) if callable(ttl_seconds) else ttl_seconds
                await self._cache.set(cache_key, result, ttl_seconds=actual_ttl)

            return result
        return wrapper
    return decorator

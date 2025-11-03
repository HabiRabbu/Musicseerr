import asyncio
import time
from typing import Any, Callable, Optional
from functools import wraps


class CacheEntry:
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class InMemoryCache:
    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._write_lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            asyncio.create_task(self._delete_unlocked(key))
            return None
        return entry.value

    async def _delete_unlocked(self, key: str):
        async with self._write_lock:
            self._cache.pop(key, None)

    async def set(self, key: str, value: Any, ttl_seconds: int = 60):
        async with self._write_lock:
            self._cache[key] = CacheEntry(value, ttl_seconds)

    async def delete(self, key: str):
        async with self._write_lock:
            self._cache.pop(key, None)

    async def clear(self):
        async with self._write_lock:
            self._cache.clear()

    async def cleanup_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
        
        if expired_keys:
            async with self._write_lock:
                for key in expired_keys:
                    self._cache.pop(key, None)
    
    def size(self) -> int:
        return len(self._cache)


_cache = InMemoryCache()


def get_cache() -> InMemoryCache:
    return _cache


def make_cache_key(*args, **kwargs) -> str:
    parts = [str(arg) for arg in args]
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
    return ":".join(parts)


def cached(ttl_seconds: int = 60, key_prefix: str = ""):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            cached_value = await _cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            asyncio.create_task(_cache.set(cache_key, result, ttl_seconds))
            
            return result
        
        return wrapper
    return decorator


async def _cleanup_cache_periodically(interval: int = 300):
    while True:
        await asyncio.sleep(interval)
        await _cache.cleanup_expired()


def start_cache_cleanup_task():
    asyncio.create_task(_cleanup_cache_periodically())


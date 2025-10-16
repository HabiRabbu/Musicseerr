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
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.is_expired():
                    del self._cache[key]
                    return None
                return entry.value
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 60):
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds)

    async def delete(self, key: str):
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self):
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self):
        async with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]


_cache = InMemoryCache()


def get_cache() -> InMemoryCache:
    return _cache


def cached(ttl_seconds: int = 60, key_prefix: str = ""):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{str(args)}:{str(kwargs)}"
            
            cached_value = await _cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            await _cache.set(cache_key, result, ttl_seconds)
            return result
        
        return wrapper
    return decorator


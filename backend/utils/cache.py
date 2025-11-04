"""In-memory caching system with TTL support."""
import asyncio
import logging
import time
from typing import Any, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CacheEntry:
    """A cache entry with expiration time."""
    
    __slots__ = ('value', 'expires_at')
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expires_at


class InMemoryCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache, returning None if not found or expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        if entry.is_expired():
            asyncio.create_task(self.delete(key))
            return None
        
        return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set a value in cache with TTL."""
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds)

    async def delete(self, key: str) -> None:
        """Delete a key from cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    async def clear_prefix(self, prefix: str) -> int:
        """Clear all cache entries with a given prefix. Returns count removed."""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
        
        if keys_to_remove:
            async with self._lock:
                for key in keys_to_remove:
                    self._cache.pop(key, None)
            logger.info(f"Cleared {len(keys_to_remove)} cache entries with prefix '{prefix}'")
        
        return len(keys_to_remove)

    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
        
        if expired_keys:
            async with self._lock:
                for key in expired_keys:
                    self._cache.pop(key, None)
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def size(self) -> int:
        """Get the number of entries in cache."""
        return len(self._cache)


_cache = InMemoryCache()


def get_cache() -> InMemoryCache:
    """Get the global cache instance."""
    return _cache


def make_cache_key(*args, **kwargs) -> str:
    """Create a cache key from arguments."""
    parts = [str(arg) for arg in args]
    if kwargs:
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(parts)


def cached(ttl_seconds: int = 60, key_prefix: str = ""):
    """Decorator to cache function results.
    
    Args:
        ttl_seconds: Time to live in seconds
        key_prefix: Prefix for the cache key
    """
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


async def _cleanup_cache_periodically(interval: int = 300) -> None:
    """Background task to periodically clean up expired cache entries."""
    while True:
        try:
            await asyncio.sleep(interval)
            await _cache.cleanup_expired()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cache cleanup task: {e}")


def start_cache_cleanup_task() -> None:
    """Start the background cache cleanup task."""
    asyncio.create_task(_cleanup_cache_periodically())


async def clear_cache_prefix(prefix: str) -> int:
    """Clear all cache entries with a given prefix. Returns count removed."""
    return await _cache.clear_prefix(prefix)


import asyncio
import logging
import time
from typing import Any, Optional
from abc import ABC, abstractmethod
from collections import OrderedDict

logger = logging.getLogger(__name__)


class CacheInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        pass
    
    @abstractmethod
    async def clear_prefix(self, prefix: str) -> int:
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        pass
    
    @abstractmethod
    def size(self) -> int:
        pass


class CacheEntry:
    __slots__ = ('value', 'expires_at')
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class InMemoryCache(CacheInterface):
    def __init__(self, max_entries: int = 10000):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_entries = max_entries
        self._evictions = 0

    async def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        if entry.is_expired():
            asyncio.create_task(self.delete(key))
            return None
        
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
        
        return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        async with self._lock:
            if key not in self._cache and len(self._cache) >= self._max_entries:
                oldest_key, _ = self._cache.popitem(last=False)
                self._evictions += 1
                if self._evictions % 100 == 0:
                    logger.info(f"Cache LRU evictions: {self._evictions}, current size: {len(self._cache)}")
            
            self._cache[key] = CacheEntry(value, ttl_seconds)
            self._cache.move_to_end(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def clear_prefix(self, prefix: str) -> int:
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
        
        if keys_to_remove:
            async with self._lock:
                for key in keys_to_remove:
                    self._cache.pop(key, None)
            logger.info(f"Cleared {len(keys_to_remove)} cache entries with prefix '{prefix}'")
        
        return len(keys_to_remove)

    async def cleanup_expired(self) -> int:
        """Clean up expired entries. Snapshot keys to avoid iteration issues."""
        now = time.time()
        
        # Snapshot keys outside the lock to minimize lock time
        snapshot_keys = list(self._cache.keys())
        
        expired_keys = []
        for key in snapshot_keys:
            entry = self._cache.get(key)
            if entry and now > entry.expires_at:
                expired_keys.append(key)
        
        if expired_keys:
            async with self._lock:
                for key in expired_keys:
                    self._cache.pop(key, None)
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def size(self) -> int:
        return len(self._cache)

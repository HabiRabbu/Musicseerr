import asyncio
from typing import Callable
from functools import wraps
from infrastructure.cache.memory_cache import CacheInterface


def make_cache_key(*args, **kwargs) -> str:
    parts = [str(arg) for arg in args]
    if kwargs:
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(parts)


def cached(cache: CacheInterface, ttl_seconds: int = 60, key_prefix: str = ""):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            asyncio.create_task(cache.set(cache_key, result, ttl_seconds))
            
            return result
        
        return wrapper
    return decorator

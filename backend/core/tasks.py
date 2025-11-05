import asyncio
import logging
from infrastructure.cache.memory_cache import CacheInterface

logger = logging.getLogger(__name__)


async def cleanup_cache_periodically(cache: CacheInterface, interval: int = 300) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            await cache.cleanup_expired()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cache cleanup task: {e}")


def start_cache_cleanup_task(cache: CacheInterface) -> asyncio.Task:
    return asyncio.create_task(cleanup_cache_periodically(cache))

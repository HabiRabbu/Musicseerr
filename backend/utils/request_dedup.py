import asyncio
from typing import Any, Callable, TypeVar, Dict
from functools import wraps

T = TypeVar('T')

_in_flight: Dict[str, asyncio.Future] = {}
_in_flight_lock = asyncio.Lock()


def deduplicate(key_func: Callable[..., str] | None = None):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if key_func:
                request_key = f"{func.__name__}:{key_func(*args, **kwargs)}"
            else:
                request_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            
            async with _in_flight_lock:
                if request_key in _in_flight:
                    future = _in_flight[request_key]
                else:
                    future = asyncio.get_event_loop().create_future()
                    _in_flight[request_key] = future
            
            if not future.done():
                try:
                    result = await func(*args, **kwargs)
                    future.set_result(result)
                    return result
                except Exception as e:
                    future.set_exception(e)
                    raise
                finally:
                    async with _in_flight_lock:
                        _in_flight.pop(request_key, None)
            else:
                return await future
        
        return wrapper
    return decorator

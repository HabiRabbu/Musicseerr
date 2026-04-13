import asyncio
import logging
import random
import time
from enum import Enum
from functools import wraps
from typing import Awaitable, Callable, TypeVar, ParamSpec, Optional

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


CircuitStateChangeCallback = Callable[["CircuitBreaker", CircuitState, CircuitState, str], None]


class CircuitBreaker:
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        name: str = "default",
        on_state_change: CircuitStateChangeCallback | None = None,
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name
        self._on_state_change = on_state_change
        self._lock = asyncio.Lock()
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.state = CircuitState.CLOSED

    def _notify_state_change(
        self,
        previous_state: CircuitState,
        new_state: CircuitState,
        reason: str,
    ) -> None:
        if previous_state == new_state or self._on_state_change is None:
            return

        try:
            self._on_state_change(self, previous_state, new_state, reason)
        except Exception:
            logger.exception(
                "Circuit breaker '%s' state change callback failed",
                self.name,
            )
    
    def is_open(self) -> bool:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                previous_state = self.state
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self._notify_state_change(previous_state, self.state, "timeout_elapsed")
                return False
            return True
        return False
    
    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                previous_state = self.state
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self._notify_state_change(previous_state, self.state, "success_threshold_reached")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(
                "Circuit breaker '%s' reopening after failure in HALF_OPEN",
                self.name,
            )
            previous_state = self.state
            self.state = CircuitState.OPEN
            self.failure_count = 0
            self.success_count = 0
            self._notify_state_change(previous_state, self.state, "half_open_failure")
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    "Circuit breaker '%s' opening after %d failures",
                    self.name,
                    self.failure_count,
                )
                previous_state = self.state
                self.state = CircuitState.OPEN
                self._notify_state_change(previous_state, self.state, "failure_threshold_reached")
    
    def get_state(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }
    
    def reset(self):
        previous_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self._notify_state_change(previous_state, self.state, "manual_reset")

    async def arecord_success(self):
        async with self._lock:
            self.record_success()

    async def arecord_failure(self):
        async with self._lock:
            self.record_failure()

    async def atry_transition(self):
        """Acquire the lock and attempt an OPEN -> HALF_OPEN transition if the timeout has elapsed."""
        if self.state != CircuitState.OPEN:
            return
        async with self._lock:
            if self.state == CircuitState.OPEN and time.time() - self.last_failure_time > self.timeout:
                previous_state = self.state
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self._notify_state_change(previous_state, self.state, "timeout_elapsed")


class CircuitOpenError(Exception):
    def __init__(self, message: str, breaker_name: str = ""):
        super().__init__(message)
        self.breaker_name = breaker_name


def _get_retry_after_seconds(exception: Exception) -> Optional[float]:
    retry_after = getattr(exception, "retry_after_seconds", None)
    if retry_after is None:
        return None
    try:
        retry_after_value = float(retry_after)
    except (TypeError, ValueError):
        return None
    if retry_after_value <= 0:
        return None
    return retry_after_value


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    circuit_breaker: Optional[CircuitBreaker] = None,
    retriable_exceptions: tuple = (Exception,),
    non_breaking_exceptions: tuple = (),
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            service_name = circuit_breaker.name if circuit_breaker else "unknown"
            func_name = func.__name__
            
            if circuit_breaker:
                await circuit_breaker.atry_transition()
                if circuit_breaker.is_open():
                    error_msg = "Circuit breaker '%s' is OPEN"
                    logger.warning(
                        error_msg,
                        circuit_breaker.name,
                        extra={"service_name": service_name, "function": func_name}
                    )
                    raise CircuitOpenError(
                        f"Circuit breaker '{circuit_breaker.name}' is OPEN",
                        breaker_name=circuit_breaker.name,
                    )
            
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    
                    if circuit_breaker:
                        await circuit_breaker.arecord_success()
                    
                    return result
                
                except retriable_exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func_name,
                            max_attempts,
                            e,
                        )
                        break

                    retry_after_override = _get_retry_after_seconds(e)
                    if retry_after_override is not None:
                        delay = retry_after_override
                    else:
                        delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                        if jitter:
                            delay *= (0.5 + random.random())
                    
                    await asyncio.sleep(delay)
            
            if circuit_breaker and last_exception:
                is_non_breaking = isinstance(last_exception, non_breaking_exceptions) if non_breaking_exceptions else False
                if not is_non_breaking:
                    await circuit_breaker.arecord_failure()

            raise last_exception
        
        return wrapper
    return decorator

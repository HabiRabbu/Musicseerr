import asyncio
import logging
import random
import time
from enum import Enum
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, Optional

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.state = CircuitState.CLOSED
    
    def is_open(self) -> bool:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return False
            return True
        return False
    
    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' closing after {self.success_count} successes")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker '{self.name}' reopening after failure in HALF_OPEN")
            self.state = CircuitState.OPEN
            self.failure_count = 0
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker '{self.name}' opening after {self.failure_count} failures"
                )
                self.state = CircuitState.OPEN
    
    def get_state(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }


class CircuitOpenError(Exception):
    pass


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    circuit_breaker: Optional[CircuitBreaker] = None,
    retriable_exceptions: tuple = (Exception,)
):
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            service_name = circuit_breaker.name if circuit_breaker else "unknown"
            func_name = func.__name__
            start_time = time.time()
            
            if circuit_breaker and circuit_breaker.is_open():
                error_msg = f"Circuit breaker '{circuit_breaker.name}' is OPEN"
                logger.warning(
                    error_msg,
                    extra={"service_name": service_name, "function": func_name}
                )
                raise CircuitOpenError(error_msg)
            
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                attempt_start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    
                    elapsed_ms = int((time.time() - attempt_start) * 1000)
                    
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    
                    if attempt > 1:
                        total_elapsed_ms = int((time.time() - start_time) * 1000)
                        logger.info(
                            f"{func_name} succeeded on attempt {attempt}/{max_attempts}",
                            extra={
                                "service_name": service_name,
                                "function": func_name,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "elapsed_ms": elapsed_ms,
                                "total_elapsed_ms": total_elapsed_ms,
                            }
                        )
                    
                    return result
                
                except retriable_exceptions as e:
                    last_exception = e
                    elapsed_ms = int((time.time() - attempt_start) * 1000)
                    
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    
                    if attempt >= max_attempts:
                        total_elapsed_ms = int((time.time() - start_time) * 1000)
                        logger.error(
                            f"{func_name} failed after {max_attempts} attempts: {e}",
                            extra={
                                "service_name": service_name,
                                "function": func_name,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "elapsed_ms": elapsed_ms,
                                "total_elapsed_ms": total_elapsed_ms,
                                "error": str(e),
                            }
                        )
                        break
                    
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"{func_name} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s...",
                        extra={
                            "service_name": service_name,
                            "function": func_name,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "elapsed_ms": elapsed_ms,
                            "retry_delay_s": f"{delay:.2f}",
                            "error": str(e),
                        }
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator

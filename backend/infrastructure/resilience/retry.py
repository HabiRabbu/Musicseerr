"""Circuit breaker and retry decorator for resilient service calls."""
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
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping requests to failing services.
    Automatically retries after a timeout period.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        name: str = "default"
    ):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes in half-open before closing
            timeout: Seconds to wait before attempting recovery
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.state = CircuitState.CLOSED
    
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return False
            return True
        return False
    
    def record_success(self):
        """Record successful call."""
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
        """Record failed call."""
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
        """Get current state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
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
    """Decorator for retrying async functions with exponential backoff and jitter.
    
    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (2.0 = double each time)
        jitter: Add random jitter to prevent thundering herd
        circuit_breaker: Optional circuit breaker instance
        retriable_exceptions: Tuple of exceptions that should trigger retry
    
    Example:
        @with_retry(max_attempts=3, circuit_breaker=my_breaker)
        async def fetch_data():
            return await external_api_call()
    """
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

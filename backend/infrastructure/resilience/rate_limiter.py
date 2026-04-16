import asyncio
import math
import time
from typing import Optional

EPSILON = 1e-9


class TokenBucketRateLimiter:
    
    def __init__(self, rate: float, capacity: Optional[int] = None):
        self.rate = rate
        self.capacity = capacity or int(rate * 2)
        self._tokens = float(self.capacity)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        if tokens > self.capacity:
            raise ValueError(
                f"Cannot acquire {tokens} tokens (capacity: {self.capacity}). "
                f"Request would wait indefinitely."
            )
        
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                self._last_update = now
                
                if self._tokens >= tokens - EPSILON:
                    self._tokens -= tokens
                    return
                
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate
            
            await asyncio.sleep(wait_time)
    
    async def try_acquire(self, tokens: int = 1) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_update = now
            
            if self._tokens >= tokens - EPSILON:
                self._tokens -= tokens
                return True
            return False
    
    def _refresh_tokens(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_update = now

    @property
    def remaining(self) -> int:
        self._refresh_tokens()
        return max(0, int(self._tokens))

    def retry_after(self, tokens: int = 1) -> float:
        self._refresh_tokens()
        if self._tokens >= tokens - EPSILON:
            return 0.0
        deficit = tokens - self._tokens
        return math.ceil(deficit / self.rate)

    def reset(self) -> None:
        self._tokens = float(self.capacity)
        self._last_update = time.monotonic()
    
    def update_capacity(self, new_capacity: int) -> None:
        self.capacity = new_capacity
        self._tokens = min(self._tokens, float(new_capacity))

    def update_rate(self, new_rate: float) -> None:
        """Update the token refill rate (tokens/sec)."""
        if new_rate <= 0:
            raise ValueError(f"Rate must be positive, got {new_rate}")
        self.rate = new_rate

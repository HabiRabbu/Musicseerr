import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from infrastructure.degradation import (
    init_degradation_context,
    try_get_degradation_context,
    clear_degradation_context,
)
from infrastructure.resilience.rate_limiter import TokenBucketRateLimiter
from infrastructure.msgspec_fastapi import MsgSpecJSONResponse

logger = logging.getLogger(__name__)

SLOW_REQUEST_THRESHOLD = 1.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process token-bucket rate limiter with per-path overrides."""

    def __init__(
        self,
        app: ASGIApp,
        default_rate: float = 30.0,
        default_capacity: int = 60,
        overrides: dict[str, tuple[float, int]] | None = None,
    ):
        super().__init__(app)
        self._default = TokenBucketRateLimiter(rate=default_rate, capacity=default_capacity)
        self._overrides: list[tuple[str, TokenBucketRateLimiter]] = []
        for prefix, (rate, capacity) in (overrides or {}).items():
            self._overrides.append((prefix, TokenBucketRateLimiter(rate=rate, capacity=capacity)))

    def _get_limiter(self, path: str) -> TokenBucketRateLimiter:
        for prefix, limiter in self._overrides:
            if path.startswith(prefix):
                return limiter
        return self._default

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        limiter = self._get_limiter(path)
        acquired = await limiter.try_acquire()

        if acquired:
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limiter.capacity)
            response.headers["X-RateLimit-Remaining"] = str(limiter.remaining)
            return response

        retry_after = limiter.retry_after()
        return MsgSpecJSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests",
                    "details": None,
                }
            },
            headers={
                "Retry-After": str(int(retry_after)),
                "X-RateLimit-Limit": str(limiter.capacity),
                "X-RateLimit-Remaining": "0",
            },
        )


class DegradationMiddleware(BaseHTTPMiddleware):
    """Initialise a per-request DegradationContext and surface results in a header."""

    async def dispatch(self, request: Request, call_next):
        init_degradation_context()
        try:
            response = await call_next(request)
            ctx = try_get_degradation_context()
            if ctx and ctx.has_degradation():
                sources = ",".join(
                    name for name, status in ctx.summary().items() if status != "ok"
                )
                if sources:
                    response.headers["X-Degraded-Services"] = sources
            return response
        finally:
            clear_degradation_context()


class PerformanceMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        response.headers["X-Response-Time"] = f"{process_time:.3f}s"

        if process_time > SLOW_REQUEST_THRESHOLD:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}s"
            )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


# Paths that are always accessible regardless of auth state
_AUTH_EXEMPT = {
    "/health",
    "/api/v1/auth/status",
    "/api/v1/auth/login",
    "/api/v1/auth/setup",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """When auth is enabled, require a valid Bearer JWT for all API routes."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Non-API paths (frontend assets, static files) — always pass through
        if not path.startswith("/api/"):
            return await call_next(request)

        # Exempt endpoints
        if path in _AUTH_EXEMPT:
            return await call_next(request)

        from core.dependencies import get_auth_service
        auth = get_auth_service()

        if not auth.is_auth_enabled():
            return await call_next(request)

        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token[7:]

        if not token or not auth.validate_token(token):
            return MsgSpecJSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Authentication required",
                        "details": None,
                    }
                },
            )

        return await call_next(request)

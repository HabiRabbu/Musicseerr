import logging
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
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

_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/v1/auth/",
    "/api/v1/docs",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
    "/api/v1/auth/oidc/callback",
    "/api/v1/auth/oidc/exchange",
)


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


class AuthMiddleware(BaseHTTPMiddleware):
    """Global Bearer token validation for all /api/* routes.
 
    Non-/api/* paths (frontend SPA, static assets) are skipped entirely.
    Public API routes are allowlisted above. All others return 401 if the
    token is missing, invalid, or expired.
 
    On success, injects into request.state:
        - user: UserRecord
        - token: TokenRecord
    """
 
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
 
        # Non-API paths: SPA routes, static files, favicons, etc.
        if not path.startswith("/api/") and path != "/health":
            return await call_next(request)
 
        # Allowlisted public API routes
        if self._is_public(path):
            return await call_next(request)
 
        # All other /api/* routes require a valid token
        raw_token = self._extract_bearer(request)
        if not raw_token:
            return self._unauthorized("Not authenticated")
 
        # Lazy import to avoid circular imports at module load time
        from core.dependencies.auth_providers import get_auth_service
        auth_service = get_auth_service()
 
        result = await auth_service.verify_token(raw_token)
        if result is None:
            return self._unauthorized("Invalid or expired token")
 
        user, token = result
        request.state.user = user
        request.state.token = token
 
        return await call_next(request)

    @staticmethod
    def _is_public(path: str) -> bool:
        for prefix in _PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    @staticmethod
    def _extract_bearer(request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip() or None
        return None

    @staticmethod
    def _unauthorized(detail: str) -> MsgSpecJSONResponse:
        return MsgSpecJSONResponse(
            status_code = status.HTTP_401_UNAUTHORIZED,
            content = {"error": {"code": "UNAUTHORIZED", "message": detail, "details": None}},
            headers = {"WWW-Authenticate": "Bearer"},
        )


def _get_current_user(request: Request):
    """Extract the already verified user from request.state.
 
    The middleware has already validated the token by the time any route
    handler runs, so this is a zero-cost lookup with no DB call.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated",
            headers = {"WWW-Authenticate": "Bearer"},
        )
    return user


def _get_current_admin(request: Request):
    """Like _get_current_user but also enforces admin role."""
    user = _get_current_user(request)
    if user.role != "admin":
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail = "Admin access required",
        )
    return user


def _get_current_token(request: Request):
    """Extract the already verified token record from request.state."""
    token = getattr(request.state, "token", None)
    if token is None:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated",
            headers = {"WWW-Authenticate": "Bearer"},
        )
    return token


CurrentUserDep = Annotated[object, Depends(_get_current_user)]
CurrentAdminDep = Annotated[object, Depends(_get_current_admin)]
CurrentTokenDep = Annotated[object, Depends(_get_current_token)]

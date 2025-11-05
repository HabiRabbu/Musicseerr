"""Global exception handlers for FastAPI application."""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from core.exceptions import ResourceNotFoundError, ExternalServiceError
from infrastructure.resilience.retry import CircuitOpenError

logger = logging.getLogger(__name__)


async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    """Handle 404 resource not found errors."""
    logger.warning(f"Resource not found: {exc} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def external_service_error_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
    """Handle external service errors (Lidarr, MusicBrainz, etc.)."""
    logger.error(f"External service error: {exc} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"External service error: {exc}"},
    )


async def circuit_open_error_handler(request: Request, exc: CircuitOpenError) -> JSONResponse:
    """Handle circuit breaker open errors."""
    logger.error(f"Circuit breaker open: {exc} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"Service temporarily unavailable: {exc}"},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.exception(f"Unexpected error: {exc} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

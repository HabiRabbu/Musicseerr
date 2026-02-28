import logging
from fastapi import Request, status
from core.exceptions import ResourceNotFoundError, ExternalServiceError, ValidationError
from infrastructure.msgspec_fastapi import MsgSpecJSONResponse
from infrastructure.resilience.retry import CircuitOpenError

logger = logging.getLogger(__name__)


async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> MsgSpecJSONResponse:
    logger.warning("Resource not found: %s - %s %s", exc, request.method, request.url.path)
    return MsgSpecJSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def external_service_error_handler(request: Request, exc: ExternalServiceError) -> MsgSpecJSONResponse:
    logger.error("External service error: %s - %s %s", exc, request.method, request.url.path)
    return MsgSpecJSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"External service error: {exc}"},
    )


async def circuit_open_error_handler(request: Request, exc: CircuitOpenError) -> MsgSpecJSONResponse:
    logger.error("Circuit breaker open: %s - %s %s", exc, request.method, request.url.path)
    return MsgSpecJSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"Service temporarily unavailable: {exc}"},
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> MsgSpecJSONResponse:
    logger.warning("Validation error: %s - %s %s", exc, request.method, request.url.path)
    return MsgSpecJSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def general_exception_handler(request: Request, exc: Exception) -> MsgSpecJSONResponse:
    logger.exception("Unexpected error: %s - %s %s", exc, request.method, request.url.path)
    return MsgSpecJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

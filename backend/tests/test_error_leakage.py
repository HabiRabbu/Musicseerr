"""Tests that exception handlers do not leak internal details."""

import pytest
from fastapi import FastAPI
import httpx

from core.exceptions import ExternalServiceError
from core.exception_handlers import (
    external_service_error_handler,
    circuit_open_error_handler,
    general_exception_handler,
)
from infrastructure.resilience.retry import CircuitOpenError


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/raise-general")
    async def raise_general():
        raise RuntimeError("secret internal path /app/main.py")

    @app.get("/raise-external")
    async def raise_external():
        raise ExternalServiceError("connection to 10.0.0.5:8096 refused")

    @app.get("/raise-circuit")
    async def raise_circuit():
        raise CircuitOpenError(
            "Circuit breaker 'jellyfin' is OPEN",
            breaker_name="jellyfin",
        )

    app.add_exception_handler(ExternalServiceError, external_service_error_handler)
    app.add_exception_handler(CircuitOpenError, circuit_open_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    return app


@pytest.mark.asyncio
async def test_general_exception_handler_hides_details():
    app = _build_app()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-general")

    body = resp.json()
    assert resp.status_code == 500
    assert body["error"]["message"] == "Internal server error"
    assert "/app/main.py" not in resp.text


@pytest.mark.asyncio
async def test_external_service_error_hides_details():
    app = _build_app()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-external")

    body = resp.json()
    assert resp.status_code == 503
    assert body["error"]["message"] == "External service unavailable"
    assert "10.0.0.5" not in resp.text


@pytest.mark.asyncio
async def test_circuit_open_error_hides_details():
    app = _build_app()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-circuit")

    body = resp.json()
    assert resp.status_code == 503
    assert body["error"]["message"] == "Jellyfin is temporarily unavailable due to repeated connection failures. Check your settings or wait for the service to recover."
    assert "circuit breaker" not in resp.text.lower() or "CIRCUIT_BREAKER_OPEN" in resp.text


@pytest.mark.asyncio
async def test_circuit_open_error_without_breaker_name_falls_back():
    app = FastAPI()

    @app.get("/raise-circuit-unnamed")
    async def raise_circuit_unnamed():
        raise CircuitOpenError("CB tripped")

    app.add_exception_handler(CircuitOpenError, circuit_open_error_handler)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-circuit-unnamed")

    body = resp.json()
    assert resp.status_code == 503
    assert body["error"]["message"].startswith("Service is temporarily unavailable")

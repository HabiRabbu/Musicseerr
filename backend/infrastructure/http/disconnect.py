from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.exceptions import ClientDisconnectedError

DisconnectCallable = Callable[[], Awaitable[bool]]


async def check_disconnected(
    is_disconnected: DisconnectCallable | None,
) -> None:
    if is_disconnected is not None and await is_disconnected():
        raise ClientDisconnectedError("Client disconnected")

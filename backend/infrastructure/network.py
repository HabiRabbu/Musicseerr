"""Bind helpers so the HTTP server answers on IPv4 and IPv6 alike."""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND_HOST_ENV = "BIND_HOST"
IPV4_WILDCARD_HOST = "0.0.0.0"
IPV6_WILDCARD_HOST = "::"
LOOPBACK_PROBE_HOSTS = ("127.0.0.1", "::1")

# asyncio's create_server() forces IPV6_V6ONLY on, so "::" serves IPv6 only and
# never accepts v4-mapped peers. The empty host is the one value that makes it
# bind a separate wildcard socket per available family.
ALL_FAMILIES_HOST = ""

_AUTO = "auto"


def dual_stack_supported() -> bool:
    """Bind both wildcards for real rather than trusting capability flags: with
    net.ipv6.conf.all.disable_ipv6=1 an AF_INET6 socket still opens but refuses
    to bind, and uvicorn exits when any listener fails."""
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as v6:
            v6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            v6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            v6.bind((IPV6_WILDCARD_HOST, 0))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as v4:
                v4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                v4.bind((IPV4_WILDCARD_HOST, v6.getsockname()[1]))
    except OSError:
        return False
    return True


def resolve_bind_host() -> str:
    configured = os.getenv(BIND_HOST_ENV, "").strip()
    if configured and configured.lower() != _AUTO:
        return configured
    return ALL_FAMILIES_HOST if dual_stack_supported() else IPV4_WILDCARD_HOST


class _IPv6ThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


class _DualStackThreadingHTTPServer(_IPv6ThreadingHTTPServer):
    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def wildcard_http_server(
    port: int, handler: Callable[..., BaseHTTPRequestHandler]
) -> ThreadingHTTPServer:
    """ThreadingHTTPServer takes a single address, so one IPV6_V6ONLY-off socket
    stands in for the pair asyncio would open for ``ALL_FAMILIES_HOST``."""
    host = resolve_bind_host()
    if host == ALL_FAMILIES_HOST:
        try:
            return _DualStackThreadingHTTPServer((IPV6_WILDCARD_HOST, port), handler)
        except OSError:
            host = IPV4_WILDCARD_HOST
    server_class = _IPv6ThreadingHTTPServer if ":" in host else ThreadingHTTPServer
    return server_class((host, port), handler)

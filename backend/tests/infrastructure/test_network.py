import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

import pytest

from infrastructure import network


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format: str, *args: object) -> None:
        return


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_bind_host_defaults_to_every_family_when_both_wildcards_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(network.BIND_HOST_ENV, raising=False)
    monkeypatch.setattr(network, "dual_stack_supported", lambda: True)

    assert network.resolve_bind_host() == ""


def test_bind_host_falls_back_to_ipv4_when_ipv6_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(network.BIND_HOST_ENV, raising=False)
    monkeypatch.setattr(network, "dual_stack_supported", lambda: False)

    assert network.resolve_bind_host() == "0.0.0.0"


@pytest.mark.parametrize("configured", ["0.0.0.0", "::1", "192.168.1.5"])
def test_bind_host_honours_an_explicit_override(
    monkeypatch: pytest.MonkeyPatch, configured: str
) -> None:
    monkeypatch.setenv(network.BIND_HOST_ENV, configured)
    monkeypatch.setattr(network, "dual_stack_supported", lambda: True)

    assert network.resolve_bind_host() == configured


def test_bind_host_treats_auto_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(network.BIND_HOST_ENV, " AUTO ")
    monkeypatch.setattr(network, "dual_stack_supported", lambda: False)

    assert network.resolve_bind_host() == "0.0.0.0"


@pytest.mark.skipif(
    not network.dual_stack_supported(), reason="host has no dual-stack IPv6"
)
def test_wildcard_server_answers_on_both_families(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(network.BIND_HOST_ENV, raising=False)
    port = _free_port()
    server = network.wildcard_http_server(port, _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for host in ("127.0.0.1", "[::1]"):
            with urlopen(f"http://{host}:{port}/", timeout=2) as response:
                assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_wildcard_server_falls_back_when_ipv6_bind_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(network.BIND_HOST_ENV, raising=False)
    monkeypatch.setattr(network, "dual_stack_supported", lambda: True)

    def refuse(*_args: object, **_kwargs: object):
        raise OSError("IPv6 unavailable")

    monkeypatch.setattr(network, "_DualStackThreadingHTTPServer", refuse)
    port = _free_port()
    server = network.wildcard_http_server(port, _Handler)
    try:
        assert server.socket.family == socket.AF_INET
    finally:
        server.server_close()


def test_wildcard_server_honours_an_explicit_ipv6_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(network.BIND_HOST_ENV, "::1")
    server = network.wildcard_http_server(_free_port(), _Handler)
    try:
        assert server.socket.family == socket.AF_INET6
    finally:
        server.server_close()


@pytest.mark.skipif(
    not network.dual_stack_supported(), reason="host has no dual-stack IPv6"
)
def test_uvicorn_serves_both_families_on_the_resolved_bind_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plausible-looking "::" passes every unit check above and still refuses
    every IPv4 client, so pin the choice against uvicorn's real socket setup."""
    monkeypatch.delenv(network.BIND_HOST_ENV, raising=False)
    (tmp_path / "stub_asgi.py").write_text(
        "async def app(scope, receive, send):\n"
        "    if scope['type'] != 'http':\n"
        "        return\n"
        "    await send({'type': 'http.response.start', 'status': 200, 'headers': []})\n"
        "    await send({'type': 'http.response.body', 'body': b'ok'})\n",
        encoding="utf-8",
    )
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "stub_asgi:app",
            "--host",
            network.resolve_bind_host(),
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=tmp_path,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            assert process.poll() is None, "uvicorn exited before binding"
            try:
                urlopen(f"http://127.0.0.1:{port}/", timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        for host in ("127.0.0.1", "[::1]"):
            with urlopen(f"http://{host}:{port}/", timeout=5) as response:
                assert response.status == 200
    finally:
        process.terminate()
        process.wait(timeout=15)

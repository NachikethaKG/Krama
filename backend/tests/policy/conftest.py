"""Pytest fixtures for policy tests: local ephemeral HTTP fixture server."""

from __future__ import annotations

import threading
from collections.abc import Generator
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class EphemeralFixtureServer:
    """Threaded local HTTP server serving test HTML fixtures from a given directory."""

    def __init__(self, directory: Path | None = None, host: str = "127.0.0.1", port: int = 0) -> None:
        self.directory = directory or FIXTURES_DIR
        self.host = host
        self.requested_port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

        target_dir = str(self.directory)

        class _SilentFixtureHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=target_dir, **kwargs)

            def log_message(self, format: str, *args: Any) -> None:
                # Suppress noisy HTTP request logging during automated pytest runs
                pass

        self._handler_cls = _SilentFixtureHandler

    def start(self) -> str:
        """Start the HTTP server on a background daemon thread and return the base URL."""
        if self._server is not None:
            return self.base_url

        self._server = HTTPServer((self.host, self.requested_port), self._handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        """Shut down the server and wait for the thread to exit."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("Server is not running")
        return int(self._server.server_port)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def __enter__(self) -> EphemeralFixtureServer:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


@pytest.fixture(scope="session")
def injection_server() -> Generator[str, None, None]:
    """Session-scoped ephemeral HTTP server serving policy fixtures at http://127.0.0.1:<port>."""
    server = EphemeralFixtureServer()
    base_url = server.start()
    try:
        yield base_url
    finally:
        server.stop()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

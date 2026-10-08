import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

# A tiny real website for end-to-end runs without Gitea: real HTTP, real navigations.
PAGES: dict[str, str] = {
    "/": """<!doctype html><title>Home</title><main><h1>Home</h1>
        <a href="/form">New item</a>
        <a href="/slow">Slow page</a></main>""",
    "/form": """<!doctype html><title>New item</title><main><h1>New item</h1>
        <form action="/done" method="post">
          <label>Item name * <input name="item"></label>
          <label>Password <input name="pw" type="password"></label>
          <label><input type="checkbox" name="init"> Add a README</label>
          <button type="submit">Create item</button>
        </form></main>""",
    "/done": "<!doctype html><title>Item created</title><main><h1>Item created</h1></main>",
    # Navigates on its own after 600 ms: verification must wait for it instead of failing at once.
    "/slow": """<!doctype html><title>Slow</title><main><h1>Slow</h1>
        <script>setTimeout(() => { location.href = "/done" }, 600)</script></main>""",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = PAGES.get(urlsplit(self.path).path)
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((body or "<title>Not found</title>").encode())

    def do_POST(self) -> None:
        # Like a real form: the body (with the password) is discarded and the browser is redirected.
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(303)
        self.send_header("Location", "/done")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

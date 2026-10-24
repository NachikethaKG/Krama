"""CSRF defense for the cookie-signed-in JSON API (#94; docs/research/phase-3-vishwas-accounts-and-csrf.md).

SameSite=Lax alone isn't enough: every localhost port is the same site. So a request that changes something
(POST/PUT/PATCH/DELETE) must
- carry `X-Krama: 1`: a page on another origin can't add a custom header without a CORS preflight, which only
  our own frontend passes;
- not come from another site (`Sec-Fetch-Site: cross-site`), nor from an `Origin` outside CORS_ORIGINS;
- send JSON when it sends a body (form posts and text/plain are what a forged form would use).
Everything else answers 403 `forbidden`. Plain ASGI, so streamed responses (SSE) pass through untouched.
"""

from collections.abc import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.errors import error_body

UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HEADER = "x-krama"


class CsrfMiddleware:
    def __init__(self, app: ASGIApp, *, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed = {o.rstrip("/") for o in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE:
            problem = self.problem(
                {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
            )
            if problem is not None:
                body = error_body("forbidden", problem)
                headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ]
                await send({"type": "http.response.start", "status": 403, "headers": headers})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)

    def problem(self, headers: dict[str, str]) -> str | None:
        """Why this unsafe request is refused, or None if it may go ahead."""
        if headers.get("sec-fetch-site") == "cross-site":
            return "Cross-site request refused"
        origin = headers.get("origin")
        if origin is not None and origin.rstrip("/") not in self.allowed:
            return "Request from an unknown origin refused"
        if headers.get(HEADER) != "1":
            return "Missing the X-Krama header"
        has_body = int(headers.get("content-length") or 0) > 0 or "transfer-encoding" in headers
        content_type = headers.get("content-type", "").split(";")[0].strip().lower()
        if has_body and content_type != "application/json":
            return "Only JSON bodies are accepted"
        return None

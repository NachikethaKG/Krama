"""Network event listener and request summary tracker."""

from __future__ import annotations

import time
from collections import defaultdict

from playwright.async_api import Page, Request, Response

from app.observer.models import NetworkRequest, NetworkSummary


class NetworkTracker:
    """Listens to page network events and produces compact step summaries."""

    def __init__(self) -> None:
        self._page: Page | None = None
        self._request_start_times: dict[Request, float] = {}
        self._active_requests: set[Request] = set()

        self._request_count: int = 0
        self._status_codes: dict[int, int] = defaultdict(int)
        self._failed_requests: list[str] = []
        self._requests_by_type: dict[str, int] = defaultdict(int)
        self._recent_requests: list[NetworkRequest] = []

    def attach(self, page: Page) -> None:
        """Attach listeners to a Playwright page."""
        if self._page is page:
            return
        if self._page is not None:
            self.detach()

        self._page = page
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_request_failed)

    def detach(self) -> None:
        """Detach listeners from the currently tracked page."""
        if self._page is not None:
            try:
                self._page.remove_listener("request", self._on_request)
                self._page.remove_listener("response", self._on_response)
                self._page.remove_listener("requestfailed", self._on_request_failed)
            except Exception:
                # Page or context may already be closed
                pass
            self._page = None

    def _on_request(self, request: Request) -> None:
        try:
            self._request_count += 1
            self._request_start_times[request] = time.monotonic()
            self._active_requests.add(request)
            res_type = request.resource_type or "other"
            self._requests_by_type[res_type] += 1
        except Exception:
            pass

    def _on_response(self, response: Response) -> None:
        try:
            req = response.request
            self._active_requests.discard(req)
            status = response.status
            self._status_codes[status] += 1

            start_t = self._request_start_times.pop(req, None)
            duration_ms = (time.monotonic() - start_t) * 1000 if start_t is not None else None

            if status >= 400:
                self._failed_requests.append(f"{req.method} {req.url} -> HTTP {status}")

            # Keep a bounded list of recent detailed requests for audit/debugging
            if len(self._recent_requests) < 50:
                self._recent_requests.append(
                    NetworkRequest(
                        method=req.method,
                        url=req.url,
                        resource_type=req.resource_type or "other",
                        status=status,
                        duration_ms=duration_ms,
                        failed=status >= 400,
                    )
                )
        except Exception:
            pass

    def _on_request_failed(self, request: Request) -> None:
        try:
            self._active_requests.discard(request)
            self._request_start_times.pop(request, None)
            failure_msg = request.failure or "unknown error"
            self._failed_requests.append(f"{request.method} {request.url} failed: {failure_msg}")

            if len(self._recent_requests) < 50:
                self._recent_requests.append(
                    NetworkRequest(
                        method=request.method,
                        url=request.url,
                        resource_type=request.resource_type or "other",
                        status=None,
                        duration_ms=None,
                        failed=True,
                        error_text=str(failure_msg),
                    )
                )
        except Exception:
            pass

    def get_summary(self) -> NetworkSummary:
        """Return the current NetworkSummary."""
        return NetworkSummary(
            request_count=self._request_count,
            status_codes=dict(self._status_codes),
            failed_requests=list(self._failed_requests),
            active_connections=len(self._active_requests),
            requests_by_type=dict(self._requests_by_type),
        )

    def snapshot_and_reset(self) -> NetworkSummary:
        """Snapshot current step network summary and reset counters for next step."""
        summary = self.get_summary()

        self._request_count = 0
        self._status_codes.clear()
        self._failed_requests.clear()
        self._requests_by_type.clear()
        self._recent_requests.clear()
        self._request_start_times.clear()

        return summary

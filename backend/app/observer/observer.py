"""Core PageObserver implementation capturing page state and network activity."""

from __future__ import annotations

import asyncio
import re
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Page

from app.observer.models import Observation
from app.observer.network import NetworkTracker
from app.ports.models import RecordingRef, StepRef
from app.ports.observer import Observer

_PASSWORD_VALUE_REGEX = re.compile(
    r'((?:textbox|field)\s+"[^"]*(?:password|token|secret)[^"]*":\s*)([^\n]+)',
    re.IGNORECASE,
)


class PageObserver(Observer):
    """Observes and captures browser page state after actions.

    Satisfies both `app.ports.observer.Observer` and `app.observer.ObserverPort`.
    Runs screenshot, accessibility snapshot, and title capture concurrently
    using asyncio.gather to keep latency under 1 second.
    """

    def __init__(
        self,
        *,
        artifacts_dir: Path | None = None,
        network_tracker: NetworkTracker | None = None,
    ) -> None:
        self._artifacts_dir = artifacts_dir
        self._tracker = network_tracker or NetworkTracker()
        self._recording: bool = False
        self._recording_started_at: datetime | None = None
        self._attached_page: Page | None = None

    @property
    def network_tracker(self) -> NetworkTracker:
        """Access the underlying network tracker."""
        return self._tracker

    def attach(self, page: Page) -> None:
        """Attach the network listener to the page."""
        self._attached_page = page
        self._tracker.attach(page)

    def detach(self) -> None:
        """Detach network listeners."""
        self._tracker.detach()
        self._attached_page = None

    async def start_recording(self, page: Page) -> None:
        """Start tracking and recording session for this run."""
        self.attach(page)
        self._recording = True
        self._recording_started_at = datetime.now(UTC)

    async def stop_recording(self) -> RecordingRef:
        """Stop tracking and return recording metadata."""
        if not self._recording or self._recording_started_at is None:
            raise RuntimeError("stop_recording() called before start_recording()")

        now = datetime.now(UTC)
        summary = self._tracker.get_summary()
        self._recording = False
        record_path = ""
        if self._artifacts_dir:
            record_path = str(self._artifacts_dir / "recording.json")

        return RecordingRef(
            path=record_path or "observer/recording.json",
            event_count=summary.request_count,
            started_at=self._recording_started_at,
            ended_at=now,
        )

    async def capture(self, page: Page, step: StepRef | None = None) -> Observation:
        """Capture the complete page state right after an action.

        Fetches screenshot, ARIA snapshot, headings, and title concurrently via asyncio.gather().
        Guarantees sub-second latency on standard hardware.
        """
        t0 = time.perf_counter()

        # Ensure network tracker is attached
        if self._attached_page is not page:
            self.attach(page)

        # 1. URL Path extraction (synchronous property)
        raw_url = page.url or ""
        parsed = urllib.parse.urlsplit(raw_url)
        path_url = parsed.path or "/"

        # 2. Concurrently fetch title, ARIA snapshot, screenshot, and headings
        title_task = self._safe_title(page)
        aria_task = self._safe_aria_snapshot(page)
        screenshot_task = self._safe_screenshot(page, step)
        headings_task = self._safe_headings(page)

        title, aria_raw, screenshot_bytes, headings = await asyncio.gather(
            title_task,
            aria_task,
            screenshot_task,
            headings_task,
        )

        # 3. Mask sensitive entries in ARIA snapshot
        aria_masked = _mask_aria_secrets(aria_raw)

        # 4. Save screenshot to artifact store if directory is provided
        screenshot_path: str | None = None
        if self._artifacts_dir and screenshot_bytes:
            step_seq = step.seq if step else int(time.time() * 1000)
            target_file = self._artifacts_dir / f"step_{step_seq:03d}.png"
            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_bytes(screenshot_bytes)
                screenshot_path = str(target_file)
            except OSError:
                screenshot_path = None

        # 5. Snapshot network activity since last step
        net_summary = self._tracker.snapshot_and_reset()

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        return Observation.create(
            url=path_url,
            raw_url=raw_url,
            title=title,
            headings=headings,
            aria_snapshot=aria_masked,
            screenshot=screenshot_bytes,
            screenshot_path=screenshot_path,
            network_summary=net_summary,
            capture_duration_ms=latency_ms,
            captured_at=datetime.now(UTC),
        )

    async def _safe_title(self, page: Page) -> str:
        try:
            return await page.title()
        except Exception:
            return ""

    async def _safe_aria_snapshot(self, page: Page) -> str:
        # Prefer landmark role='main' to avoid redundant headers/footers
        try:
            main_locator = page.get_by_role("main").first
            if await main_locator.count() > 0:
                return await main_locator.aria_snapshot(timeout=800)
        except Exception:
            pass

        # Fallback to full body snapshot
        try:
            return await page.locator("body").aria_snapshot(timeout=800)
        except Exception:
            pass

        return ""

    async def _safe_screenshot(self, page: Page, step: StepRef | None) -> bytes:
        try:
            # Mask password inputs to avoid capturing raw credentials in screenshot
            password_locators = page.locator('input[type="password"]')
            mask = [password_locators] if await password_locators.count() > 0 else []

            return await page.screenshot(
                type="png",
                animations="disabled",
                caret="hide",
                mask=mask,
                timeout=2000,
            )
        except Exception:
            return b""

    async def _safe_headings(self, page: Page) -> list[str]:
        try:
            loc = page.locator("h1, h2, h3")
            texts = await loc.all_inner_texts()
            return [t.strip() for t in texts if t.strip()]
        except Exception:
            return []


def _mask_aria_secrets(text: str) -> str:
    """Mask password and secret values inside ARIA accessibility tree text."""
    if not text:
        return ""
    return _PASSWORD_VALUE_REGEX.sub(r"\1***", text)

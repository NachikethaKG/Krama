"""rrweb event streaming bridge and in-memory event accumulator."""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page

from app.observer.recorder import SessionRecorder, get_rrweb_init_script

BINDING_NAME = "__krama_rrweb_emit__"


class RRWebRecorder(SessionRecorder):
    """Bridge that collects rrweb DOM and interaction events from browser sessions."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._raw_records: list[dict[str, Any]] = []
        self._is_recording: bool = False
        self._started_at: datetime | None = None
        self._ended_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._bound_contexts: set[BrowserContext] = set()
        self._bound_pages: set[Page] = set()

    @property
    def is_recording(self) -> bool:
        """Whether the recorder is actively listening for events."""
        return self._is_recording

    @property
    def event_count(self) -> int:
        """Total count of recorded events."""
        return len(self._events)

    @property
    def started_at(self) -> datetime | None:
        """Timestamp when recording started."""
        return self._started_at

    @property
    def ended_at(self) -> datetime | None:
        """Timestamp when recording stopped."""
        return self._ended_at

    async def _handle_browser_event(self, source: dict[str, Any], payload: Any) -> None:
        """Handle incoming event from the JavaScript browser binding."""
        if not self._is_recording:
            return

        async with self._lock:
            # Payload may be direct rrweb event dict or wrapped payload envelope
            if isinstance(payload, dict):
                self._raw_records.append(payload)
                ev = payload.get("event")
                if isinstance(ev, dict):
                    self._events.append(ev)
                else:
                    self._events.append(payload)
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        self._events.append(item)

    async def attach_binding(self, target: BrowserContext | Page) -> None:
        """Expose the python bridge binding to a browser context or page."""
        if isinstance(target, BrowserContext) and target not in self._bound_contexts:
            with contextlib.suppress(Exception):
                await target.expose_binding(BINDING_NAME, self._handle_browser_event)
                self._bound_contexts.add(target)
        elif isinstance(target, Page) and target not in self._bound_pages:
            with contextlib.suppress(Exception):
                await target.expose_binding(BINDING_NAME, self._handle_browser_event)
                self._bound_pages.add(target)

    async def start(self, target: BrowserContext | Page) -> None:
        """Start listening, expose bridge binding, and inject init script across navigations."""
        self._is_recording = True
        self._started_at = datetime.now(UTC)
        self._ended_at = None

        init_script = get_rrweb_init_script()

        context = target if isinstance(target, BrowserContext) else getattr(target, "context", None)

        if context is not None:
            if context not in self._bound_contexts:
                with contextlib.suppress(Exception):
                    await context.expose_binding(BINDING_NAME, self._handle_browser_event)
                    self._bound_contexts.add(context)
                with contextlib.suppress(Exception):
                    await context.add_init_script(script=init_script)

            # Inject into all currently open pages in this context
            for page in context.pages:
                await self._inject_into_page(page, init_script)

        elif isinstance(target, Page):
            if target not in self._bound_pages:
                with contextlib.suppress(Exception):
                    await target.expose_binding(BINDING_NAME, self._handle_browser_event)
                    self._bound_pages.add(target)
                with contextlib.suppress(Exception):
                    await target.add_init_script(script=init_script)

            await self._inject_into_page(target, init_script)

    async def _inject_into_page(self, page: Page, script: str) -> None:
        """Safely evaluate the init script on a live page if not already recording."""
        with contextlib.suppress(Exception):
            if not page.is_closed():
                await page.evaluate(script)

    async def stop(self) -> list[dict[str, Any]]:
        """Stop listening and return recorded events in chronological order."""
        if not self._is_recording:
            return list(self._events)

        self._is_recording = False
        self._ended_at = datetime.now(UTC)
        return self.get_events()

    def get_events(self) -> list[dict[str, Any]]:
        """Return a copy of all collected rrweb events sorted by timestamp if available."""
        return sorted(self._events, key=lambda ev: ev.get("timestamp", 0))

    def get_raw_records(self) -> list[dict[str, Any]]:
        """Return raw event envelopes including doc_id and sequence metadata."""
        return list(self._raw_records)

    def clear(self) -> None:
        """Clear all in-memory events and reset timestamps."""
        self._events.clear()
        self._raw_records.clear()
        self._started_at = None
        self._ended_at = None

    def save_to_json(self, file_path: Path | str, *, indent: int | None = None) -> Path:
        """Save accumulated events to a JSON file.

        Creates parent directories if necessary and writes the events array as JSON.
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        events = self.get_events()
        with path.open("w", encoding="utf-8") as f:
            json.dump(events, f, indent=indent)
        return path

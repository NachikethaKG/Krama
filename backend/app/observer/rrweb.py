"""rrweb event streaming bridge and in-memory event accumulator."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import BrowserContext, Page

from app.observer.recorder import SessionRecorder

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
            try:
                await target.expose_binding(BINDING_NAME, self._handle_browser_event)
                self._bound_contexts.add(target)
            except Exception:
                # Binding may already be exposed in this context
                pass
        elif isinstance(target, Page) and target not in self._bound_pages:
            try:
                await target.expose_binding(BINDING_NAME, self._handle_browser_event)
                self._bound_pages.add(target)
            except Exception:
                pass

    async def start(self, target: BrowserContext | Page) -> None:
        """Start listening and attach event binding."""
        self._is_recording = True
        self._started_at = datetime.now(UTC)
        self._ended_at = None
        await self.attach_binding(target)

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

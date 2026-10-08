"""Observer port protocol definition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from playwright.async_api import Page

from app.observer.models import Observation
from app.ports.models import RecordingRef, StepRef


@runtime_checkable
class ObserverPort(Protocol):
    """Port interface for capturing page state after agent actions."""

    async def capture(self, page: Page, step: StepRef | None = None) -> Observation:
        """Capture the complete page state (URL, ARIA, screenshot, network)."""
        ...

    async def start_recording(self, page: Page) -> None:
        """Start the recording session for this run."""
        ...

    async def stop_recording(self) -> RecordingRef:
        """Stop recording and return reference."""
        ...

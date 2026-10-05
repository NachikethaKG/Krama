from typing import Protocol

from playwright.async_api import Page

from app.ports.models import ObservedState, RecordingRef, StepRef


class Observer(Protocol):
    """Captures what the agent sees. Implemented by `app.observer` (Nachiketha), used by the agent (Vishwas).

    One Observer instance belongs to one run.
    """

    async def capture(self, page: Page, step: StepRef) -> ObservedState:
        """Capture the page state right after `step` was performed."""
        ...

    async def start_recording(self, page: Page) -> None:
        """Start the rrweb recording for this run. Must survive page navigations."""
        ...

    async def stop_recording(self) -> RecordingRef:
        """Stop recording and store it. Raises RuntimeError if recording wasn't started."""
        ...

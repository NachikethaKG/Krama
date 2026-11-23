"""Human takeover (#131, #407, ADR 0008): the run's owner drives a paused run's live page from the web UI.

A `TakeoverSession` streams the page as JPEG frames (Playwright's screencast: frames only when the page
changes, at most 15 per second) and replays the owner's mouse, keys and pasted text on it. While it lasts,
the page may only navigate to the target and its sign-in hosts (the server's browser must not become a way
into its network), new tabs are closed, and 5 minutes without input end it. Frames live only in memory: they
are never stored, logged or sent to an LLM (T12).

What the owner did is checked on hand-back (#409); the API and the screen WebSocket are #408.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Route

from app.contracts_gen.takeover_schema import TakeoverKey, TakeoverMouse, TakeoverText

logger = logging.getLogger(__name__)

TAKEOVER_REASONS = frozenset(
    {"auth_wall", "captcha", "recovery_exhausted", "verification_unclear", "no_progress"}
)
"""Pauses a human can resolve on the page itself (T5). Never rate_limited (waiting is the answer), destructive
actions (allow/deny is the answer) or replan reviews (the steps are the question)."""

WIDTH, HEIGHT = 1280, 800
MAX_FPS = 15
QUALITY = 60
IDLE_S = 300.0

FrameSink = Callable[[bytes], Awaitable[None]]
Notice = Callable[[str], Awaitable[None]]
TakeoverInput = TakeoverMouse | TakeoverKey | TakeoverText


class TakeoverError(Exception):
    """A takeover can't start. `reason`: not_available or active."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class ScreenFeed:
    """Between a takeover session and the one screen WebSocket watching it: the newest frames (a slow viewer
    drops old ones instead of building a backlog) and notices (`blocked`, `ended`) as JSON-ready dicts."""

    def __init__(self, max_frames: int = 2) -> None:
        self._queue: asyncio.Queue[bytes | dict[str, Any]] = asyncio.Queue()
        self._max_frames = max_frames
        self._frames = 0
        self._attached = False

    def attach(self) -> bool:
        """One viewer per takeover: False if one is attached already."""
        if self._attached:
            return False
        self._attached = True
        return True

    def detach(self) -> None:
        self._attached = False

    @property
    def attached(self) -> bool:
        return self._attached

    async def frame(self, data: bytes) -> None:
        if self._frames >= self._max_frames:
            return  # the viewer is behind: skip this one, the next change sends a fresh frame
        self._frames += 1
        await self._queue.put(data)

    async def blocked(self, message: str) -> None:
        await self._queue.put({"type": "blocked", "message": message})

    async def ended(self, reason: str) -> None:
        await self._queue.put({"type": "ended", "reason": reason})

    async def next(self) -> bytes | dict[str, Any]:
        item = await self._queue.get()
        if isinstance(item, bytes):
            self._frames -= 1
        return item


def host_of(url: str) -> str:
    """`host[:port]`, lower case: what navigation is checked against."""
    return urlsplit(url).netloc.lower()


class TakeoverSession:
    """One owner's control of one paused page. `end` is idempotent and calls `on_end(reason)` once."""

    def __init__(
        self,
        page: Page,
        *,
        allowed_hosts: Iterable[str],
        on_end: Callable[[str], Awaitable[None]],
        on_blocked: Notice | None = None,
        max_fps: float = MAX_FPS,
        idle_s: float = IDLE_S,
        clock: Callable[[], float] = time.monotonic,
        step_seq: int = 1,
    ) -> None:
        self._page = page
        self._allowed = {h.lower() for h in allowed_hosts if h}
        self._on_end = on_end
        self._on_blocked = on_blocked
        self._min_gap = 1.0 / max_fps
        self._idle_s = idle_s
        self._clock = clock
        self._sink: FrameSink | None = None
        self._last_frame = float("-inf")
        self.step_seq = step_seq
        self.started_at = clock()
        self.last_input_at: float | None = None
        self.started_wall = datetime.now(UTC)
        self.last_input_wall: datetime | None = None
        self.ended: str | None = None
        self._watchdog: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def allowed(self, url: str) -> bool:
        """Only http(s) pages on the target and its sign-in hosts. file:, chrome:, data: and any other host (a
        private address included) are refused."""
        parts = urlsplit(url)
        return parts.scheme in ("http", "https") and parts.netloc.lower() in self._allowed

    async def start(self, on_frame: FrameSink) -> None:
        """Begin streaming to `on_frame` and guarding navigation."""
        self._sink = on_frame
        await self._page.route("**/*", self._guard)
        self._page.context.on("page", self._close_popup)
        await self._page.screencast.start(
            on_frame=self._frame, quality=QUALITY, size={"width": WIDTH, "height": HEIGHT}
        )
        self._watchdog = asyncio.create_task(self._idle_watch())

    async def handle(self, message: TakeoverInput) -> None:
        """Replay one input on the page. A key Playwright doesn't know is ignored, never fatal."""
        if self.ended is not None:
            return
        self.last_input_at = self._clock()
        self.last_input_wall = datetime.now(UTC)
        mouse, keyboard = self._page.mouse, self._page.keyboard
        try:
            match message:
                case TakeoverMouse(event="move"):
                    await mouse.move(message.x, message.y)
                case TakeoverMouse(event="down"):
                    await mouse.move(message.x, message.y)
                    await mouse.down(button=message.button or "left", click_count=message.click_count or 1)
                case TakeoverMouse(event="up"):
                    await mouse.move(message.x, message.y)
                    await mouse.up(button=message.button or "left", click_count=message.click_count or 1)
                case TakeoverMouse(event="wheel"):
                    await mouse.move(message.x, message.y)
                    await mouse.wheel(message.delta_x or 0, message.delta_y or 0)
                case TakeoverKey(event="down"):
                    await keyboard.down(message.key)
                case TakeoverKey(event="up"):
                    await keyboard.up(message.key)
                case TakeoverText():
                    await keyboard.insert_text(message.text)
        except PlaywrightError as e:
            logger.info(
                "takeover input ignored: %s", type(e).__name__
            )  # never the input itself: it may be a secret

    async def end(self, reason: str) -> None:
        """Stop streaming and guarding; the page stays as the owner left it."""
        async with self._lock:
            if self.ended is not None:
                return
            self.ended = reason
        if self._watchdog is not None and self._watchdog is not asyncio.current_task():
            self._watchdog.cancel()
        self._page.context.remove_listener("page", self._close_popup)
        for stop in (self._page.screencast.stop, lambda: self._page.unroute("**/*", self._guard)):
            with contextlib.suppress(PlaywrightError):  # the page or browser is already gone
                await stop()
        self._sink = None
        await self._on_end(reason)

    async def _frame(self, frame: Any) -> None:
        now = self._clock()
        if self._sink is None or now - self._last_frame < self._min_gap:
            return  # over the fps cap: Playwright acks it and sends the next change
        self._last_frame = now
        try:
            await self._sink(frame["data"])
        except Exception:  # the viewer went away; the WebSocket side ends the takeover
            logger.debug("takeover frame not delivered", exc_info=True)

    async def _guard(self, route: Route) -> None:
        request = route.request
        if (
            request.is_navigation_request()
            and request.frame == self._page.main_frame
            and not self.allowed(request.url)
        ):
            await route.abort("aborted")  # a cancelled navigation: no error page, the owner stays put
            if self._on_blocked is not None:
                await self._on_blocked(f"Krama only opens pages on {', '.join(sorted(self._allowed))} here.")
            return
        await route.fallback()

    async def _close_popup(self, popup: Page) -> None:
        await popup.close()
        if self._on_blocked is not None:
            await self._on_blocked("New tabs and windows are closed during a takeover.")

    async def _idle_watch(self) -> None:
        while self.ended is None:
            since = self.last_input_at if self.last_input_at is not None else self.started_at
            left = self._idle_s - (self._clock() - since)
            if left <= 0:
                await self.end("idle")
                return
            await asyncio.sleep(min(left, 1.0))

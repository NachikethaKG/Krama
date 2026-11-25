from contextlib import suppress
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from playwright.async_api import Error as PlaywrightError

from app.agent.page_text import PAGE_BUDGET_CHARS, trim_snapshot


@dataclass(frozen=True)
class SessionConfig:
    """How to open the browser for one run.

    `base_url` is the site under test (e.g. http://localhost:3001). Navigation uses URL paths relative to it,
    the same as `url_matches` in the contract.
    """

    base_url: str
    viewport_width: int = 1280
    viewport_height: int = 800
    device_scale_factor: float = 1.0
    """CSS px stay the same at any scale; only screenshots get `scale` times more pixels."""
    headless: bool = True
    # Playwright's default is 30 s, far too long to notice that one agent step failed.
    action_timeout_ms: int = 5_000
    navigation_timeout_ms: int = 15_000
    storage_state: dict[str, Any] | None = None
    """A stored signed-in session (cookies + localStorage, #87) to open the context with. A secret."""


class PlaywrightSession:
    """One headless Chromium browser with one page, for one run.

    Use it as an async context manager; everything is closed on exit, also after an error.
    """

    def __init__(self, config: SessionConfig) -> None:
        self.config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("PlaywrightSession is not open; use `async with PlaywrightSession(...)`")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("PlaywrightSession is not open; use `async with PlaywrightSession(...)`")
        return self._context

    async def __aenter__(self) -> Self:
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
            self._context = await self._browser.new_context(
                base_url=self.config.base_url,
                viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
                device_scale_factor=self.config.device_scale_factor,
                storage_state=self.config.storage_state,  # type: ignore[arg-type]
            )
            self._context.set_default_timeout(self.config.action_timeout_ms)
            self._context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
            self._page = await self._context.new_page()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._page = self._context = self._browser = self._playwright = None


# Open dialogs. Many sites (Gitea's Fomantic UI among them) render them outside <main>, without role=dialog.
OPEN_DIALOGS = "dialog[open], [role=dialog], [role=alertdialog], .ui.modal.visible"


def _as_dialog(snapshot: str) -> str:
    """The dialog's ARIA lines under a `- dialog:` line, as Playwright prints a real role=dialog."""
    lines = snapshot.splitlines()
    if lines and lines[0].lstrip().startswith(("- dialog", "- alertdialog")):
        return snapshot
    return "\n".join(["- dialog:", *(f"  {line}" for line in lines)])


async def page_snapshot(page: Page, budget: int = PAGE_BUDGET_CHARS) -> str:
    """ARIA snapshot of the whole page for an LLM (planner, task check), trimmed to `budget` characters.

    The whole `body`, not only `<main>`: the header holds site search, navigation and account menus, and the
    planner never saw them (#461, spike #457). Open dialogs outside `<main>` come first, marked as dialogs, so
    trimming never drops them. Untrusted: callers mask and delimit it before an LLM sees it."""
    dialogs = "\n".join(await _dialogs_outside_main(page))
    try:
        body = await page.locator("body").aria_snapshot(timeout=5_000)
    except Exception:
        return dialogs
    if not dialogs:
        return trim_snapshot(body, budget)
    return "\n".join([dialogs, trim_snapshot(body, max(budget - len(dialogs), budget // 2))])


async def _dialogs_outside_main(page: Page) -> list[str]:
    dialogs = page.locator(OPEN_DIALOGS).filter(visible=True)
    found: list[str] = []
    try:
        for i in range(await dialogs.count()):
            dialog = dialogs.nth(i)
            if await dialog.evaluate("e => !e.closest('main, [role=main]')"):
                found.append(_as_dialog(await dialog.aria_snapshot(timeout=2_000)))
    except Exception:
        return found  # a dialog closing mid-read is not an error
    return found


def start_path(target_url: str) -> str:
    """Where a run starts on its target: the target URL's own path and query (`/todomvc`, `/3/`), else `/`.

    Navigation resolves paths against the origin, so opening `/` on `https://docs.python.org/3` lands on
    `https://docs.python.org/` and loses the `/3` the user named (spike #457, #462).
    """
    parts = urlsplit(target_url)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path


START_SETTLE_MS = 10_000
"""How long the start page may keep loading after its HTML: an app page (Trello) shows only a spinner until
its data arrives, and may then move to another URL."""


async def open_start_page(page: Page, path: str = "/") -> bool:
    """Open the site's start page, trying twice: a real site sometimes drops one load (github.com timed out
    once in the Phase 3 benchmark). False if it can't be reached, so the run says so instead of crashing.

    Then wait (at most `START_SETTLE_MS`) for the network to go quiet, so the planner and the first step see
    the page, not its loading spinner (#482: Trello's spinner read as signed out). A page that never goes
    quiet (polling, live updates) is used as it is after the wait."""
    for _ in range(2):
        try:
            await page.goto(path, wait_until="domcontentloaded")
        except PlaywrightError:
            continue
        with suppress(PlaywrightError):
            await page.wait_for_load_state("networkidle", timeout=START_SETTLE_MS)
        return True
    return False

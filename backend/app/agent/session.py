from dataclasses import dataclass
from types import TracebackType
from typing import Self

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


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


async def page_snapshot(page: Page) -> str:
    """ARIA snapshot of the current page for the planner (`main` if there is one, else `body`), plus any open
    dialog outside it. Untrusted: the planner redacts and delimits it before an LLM sees it."""
    for locator in (page.get_by_role("main").first, page.locator("body")):
        try:
            snapshot = await locator.aria_snapshot(timeout=2_000)
        except Exception:
            continue
        return "\n".join([snapshot, *await _dialogs_outside_main(page)])
    return ""


async def _dialogs_outside_main(page: Page) -> list[str]:
    dialogs = page.locator(OPEN_DIALOGS).filter(visible=True)
    found: list[str] = []
    try:
        for i in range(await dialogs.count()):
            dialog = dialogs.nth(i)
            if await dialog.evaluate("e => !e.closest('main, [role=main]')"):
                found.append(await dialog.aria_snapshot(timeout=2_000))
    except Exception:
        return found  # a dialog closing mid-read is not an error
    return found

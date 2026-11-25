"""Cookie and consent banners, cleared by code with the choice that shares least (#493).

A banner isn't part of any task. Left to the step agent, "click Only necessary" became tutorial step 1 on
Trello, and the replay broke whenever the banner looked different. So Krama answers it itself, the same way
every time, before the agent looks at the page. The answer is never a step.

It is conservative on purpose:
- It clicks only a button from `LEAST_SHARING` (Only necessary, Reject all, Decline, ...), never Accept.
- The button must sit inside a box whose text talks about cookies or consent. A "Decline" button on an
  invitation, for example, is left alone.
- When a banner offers no such button, it stays. The agent may then deal with it (DECIDE_SYSTEM's rule).

This answers a consent question on the user's behalf, in their favour. It isn't a bot check and gets around
nothing (AGENTS.md §4).
"""

import logging
import re

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Frame, Locator, Page

logger = logging.getLogger(__name__)

LEAST_SHARING = re.compile(
    r"^\s*("
    r"only necessary|necessary only|(use |allow )?(only )?necessary cookies( only)?|"
    r"only essential|essential only|(use |allow )?(only )?essential cookies( only)?|"
    r"accept only (necessary|essential)( cookies)?|"
    r"reject all|reject all cookies|reject|reject cookies|reject optional cookies|"
    r"decline|decline all|decline cookies|decline optional cookies|"
    r"deny|deny all|refuse|refuse all|"
    r"continue without accepting|disagree and close"
    r")\s*$",
    re.IGNORECASE,
)
"""The button names Krama clicks: the choices that share least. Never an "accept all"."""

_ABOUT_CONSENT = r"/cookie|consent|tracking|privacy choices/i"

# The button's nearest ancestors (up to 8 levels): is it inside a box about cookies or consent? The climb
# stops at a box with more than 3000 characters: a banner is small, while the whole page's text often says
# "cookie settings" somewhere in its footer.
_IN_CONSENT_BOX = (
    "(el, about) => { const re = new RegExp(about.slice(1, about.lastIndexOf('/')), 'i');"
    " let n = el.parentElement;"
    " for (let i = 0; i < 8 && n; i++, n = n.parentElement) {"
    "   const text = n.innerText || '';"
    "   if (text.length > 3000) return false;"
    "   if (re.test((n.getAttribute('aria-label') || '') + ' ' + text)) return true; }"
    " return false; }"
)

MAX_BANNERS = 3
"""Banners answered per call (Trello showed two copies of the same notice)."""


async def clear_consent(page: Page, *, timeout_ms: int = 2000) -> int:
    """Answer the cookie or consent banners on the page (and its frames) with the least-sharing choice.
    Returns how many were answered. Never raises: a banner Krama can't answer is left to the agent."""
    answered = 0
    for _ in range(MAX_BANNERS):
        button = await _least_sharing_button(page)
        if button is None:
            break
        try:
            # The element itself, not the locator: with two copies of a notice, the locator would find the
            # second one and never see "hidden".
            handle = await button.element_handle(timeout=timeout_ms)
            await handle.click(timeout=timeout_ms)
            await handle.wait_for_element_state("hidden", timeout=timeout_ms)
        except PlaywrightError as e:
            logger.info("consent banner on %s: couldn't answer it (%s)", page.url, type(e).__name__)
            break
        answered += 1
    if answered:
        logger.info("consent banner on %s: answered %d with the least-sharing choice", page.url, answered)
    return answered


async def _least_sharing_button(page: Page) -> Locator | None:
    for frame in [page.main_frame, *page.main_frame.child_frames]:
        found = await _in_frame(frame)
        if found is not None:
            return found
    return None


async def _in_frame(frame: Frame) -> Locator | None:
    try:
        buttons = frame.get_by_role("button", name=LEAST_SHARING)
        for i in range(await buttons.count()):
            button = buttons.nth(i)
            if await button.is_visible() and await button.evaluate(_IN_CONSENT_BOX, _ABOUT_CONSENT):
                return button
    except PlaywrightError:
        return None  # a frame that went away, or a page in the middle of navigating
    return None

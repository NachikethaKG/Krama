"""What the page offered when a step's target wasn't found: the visible elements with the planned role (#109).

Read only after a locator miss, so a run that finds its targets pays nothing. Validation (#110) stores them as
drift evidence, and self-healing (#112) scores them (docs/research/phase-4-vishwas-self-healing-locators.md).
Names come from the page: untrusted text, used as data, never as instructions.
"""

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from pydantic import BaseModel, ConfigDict

from app.agent.context import ElementContext, element_context
from app.contracts_gen.common_schema import BoundingBox

MAX_CANDIDATES = 20
"""More would make a slow failure slower (one ARIA snapshot each) without helping a human or a scorer."""
_MAX_NAME = 120


class Candidate(BaseModel):
    """One visible element with the planned role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    name: str
    """Its accessible name (or text), as the ARIA snapshot shows it."""
    bbox: BoundingBox | None = None
    """Page coordinates (CSS px), like `ActionResult.bbox`."""
    context: ElementContext | None = None


async def role_candidates(page: Page, role: str) -> list[Candidate]:
    """Up to MAX_CANDIDATES visible elements with this ARIA role, in page order. Never raises."""
    # Here, not at the top: app.verifier's package imports the agent (its run log), which imports this module.
    from app.verifier.aria import parse_aria_snapshot

    try:
        found = page.get_by_role(role).filter(visible=True)  # type: ignore[arg-type]
        count = min(await found.count(), MAX_CANDIDATES)
        scroll = await page.evaluate("[window.scrollX, window.scrollY]")
        out = []
        for i in range(count):
            element = found.nth(i)
            nodes = parse_aria_snapshot(await element.aria_snapshot())
            box = await element.bounding_box()
            out.append(
                Candidate(
                    role=role,
                    name=" ".join(nodes[0].label().split())[:_MAX_NAME] if nodes else "",
                    bbox=(box["x"] + scroll[0], box["y"] + scroll[1], box["width"], box["height"])
                    if box
                    else None,
                    context=await element_context(element),
                )
            )
        return out
    except PlaywrightError:
        return []  # the page changed while reading it: no evidence rather than a crash

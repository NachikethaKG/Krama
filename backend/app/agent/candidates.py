"""What an element looks like to a healer: role, name, container, form, stable attributes and position.

Recorded for the target of every step that ran (its fingerprint, stored with the step, D2 in
docs/research/phase-4-decisions-alignment.md), and read for the visible elements with the planned role after a
locator miss (#109), so validation (#110) can store them as drift evidence and self-healing (#112) can score
them against the fingerprint. Names and attributes come from the page: untrusted text, used as data, never as
instructions.
"""

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page
from pydantic import BaseModel, ConfigDict

from app.agent.context import ElementContext, element_context
from app.contracts_gen.common_schema import BoundingBox

MAX_CANDIDATES = 50
"""Enough for a busy settings page; reading each costs one ARIA snapshot, and only after a miss."""
_MAX_TEXT = 120

# The form an element submits (its action URL plus Gitea's hidden `action` field, which tells apart several
# forms posting to one URL) and its stable attributes. Read in one round trip.
_FACTS_JS = """e => {
  const f = e.form || e.closest('form');
  const a = f ? f.querySelector('input[name=action]') : null;
  return {
    form: f ? (f.getAttribute('action') || '') + '|' + (a ? a.value : '') : null,
    element_id: e.id || null,
    name_attr: e.getAttribute('name'),
  };
}"""


class Candidate(BaseModel):
    """One element as a healer sees it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    name: str
    """Its accessible name (or text), as the ARIA snapshot shows it."""
    bbox: BoundingBox | None = None
    """Page coordinates (CSS px), like `ActionResult.bbox`."""
    context: ElementContext | None = None
    form: str | None = None
    """The form it belongs to (action URL + hidden `action` value), or None outside a form."""
    element_id: str | None = None
    name_attr: str | None = None


async def describe_element(element: Locator, role: str) -> Candidate:
    """One element's description. Raises PlaywrightError if it went away meanwhile."""
    # Here, not at the top: app.verifier's package imports the agent (its run log), which imports this module.
    from app.verifier.aria import parse_aria_snapshot

    nodes = parse_aria_snapshot(await element.aria_snapshot())
    box = await element.bounding_box()
    scroll = await element.page.evaluate("[window.scrollX, window.scrollY]")
    facts = await element.evaluate(_FACTS_JS)
    return Candidate(
        role=nodes[0].role if nodes else role,
        name=" ".join(nodes[0].label().split())[:_MAX_TEXT] if nodes else "",
        bbox=(box["x"] + scroll[0], box["y"] + scroll[1], box["width"], box["height"]) if box else None,
        context=await element_context(element),
        form=facts.get("form"),
        element_id=(facts.get("element_id") or None) and str(facts["element_id"])[:_MAX_TEXT],
        name_attr=(facts.get("name_attr") or None) and str(facts["name_attr"])[:_MAX_TEXT],
    )


async def role_candidates(page: Page, role: str) -> list[Candidate]:
    """Up to MAX_CANDIDATES visible elements with this ARIA role, in page order. Never raises."""
    try:
        found = page.get_by_role(role).filter(visible=True)  # type: ignore[arg-type]
        count = min(await found.count(), MAX_CANDIDATES)
        return [await describe_element(found.nth(i), role) for i in range(count)]
    except PlaywrightError:
        return []  # the page changed while reading it: no evidence rather than a crash

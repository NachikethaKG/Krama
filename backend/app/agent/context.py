"""Where on the page an element sits (dialog, menu, top bar, form section), for human-readable step text.

Read from the DOM right before acting, because a dialog or menu is often gone after the click. The names come
from the page, so they are untrusted text: used only as words in the step text, never as instructions.
Rule tested on Gitea in docs/research/phase-2-vishwas-instruction-text.md (#73).
"""

from typing import Literal

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator
from pydantic import BaseModel, ConfigDict, ValidationError

type ContainerKind = Literal["dialog", "menu", "top_bar", "section"]

_MAX_NAME = 60

# 1. Inside a dialog: the dialog and its title.
# 2. Inside the page's top bar.
# 3. Inside a dropdown menu (positioned absolutely, so not a menu bar or tab strip).
# 4. Inside a form section: the heading right before one of the element's ancestors, using the heading's own
#    words. A heading made only of links (a tab strip) is navigation, not a section title.
_CONTEXT_JS = r"""el => {
  const text = e => (e.textContent || '').trim().replace(/\s+/g, ' ');
  const own = h => {
    const c = h.cloneNode(true);
    c.querySelectorAll('a, button, [role=button], [role=link]').forEach(x => x.remove());
    return text(c);
  };
  const dialog = el.closest('dialog, [role=dialog], [role=alertdialog], .ui.modal');
  if (dialog) {
    const h = dialog.querySelector('h1, h2, h3, h4, [role=heading], .header');
    return { container: 'dialog', name: h ? text(h) : null };
  }
  if (el.closest('#navbar, [role=banner], body > header')) return { container: 'top_bar', name: null };
  const menu = el.closest('[role=menu], .menu');
  if (menu && getComputedStyle(menu).position === 'absolute') return { container: 'menu', name: null };
  for (let a = el; a && a !== document.body; a = a.parentElement) {
    let s = a.previousElementSibling;
    while (s && !/^H[1-4]$/.test(s.tagName) && s.getAttribute('role') !== 'heading') {
      if (s.offsetParent !== null && text(s)) { s = null; break; }
      s = s.previousElementSibling;
    }
    if (s) return own(s) ? { container: 'section', name: own(s) } : { container: null, name: null };
  }
  return { container: null, name: null };
}"""


class ElementContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    container: ContainerKind
    name: str | None = None
    """The dialog's title or the section's heading. Untrusted page text."""


async def element_context(locator: Locator) -> ElementContext | None:
    """The element's container, or None if it has none or the page couldn't tell (never raises)."""
    try:
        found = await locator.evaluate(_CONTEXT_JS)
    except PlaywrightError:
        return None
    if not isinstance(found, dict) or not found.get("container"):
        return None
    name = found.get("name")
    name = " ".join(str(name).split())[:_MAX_NAME] or None if name else None
    try:
        return ElementContext(container=found["container"], name=name)
    except ValidationError:
        return None

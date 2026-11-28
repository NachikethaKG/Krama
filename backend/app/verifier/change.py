"""What an action visibly changed, as an expected state (#469, ADR 0011).

In step mode nobody guesses what the next page looks like. After an action, the difference between the page
before and after becomes that step's `expected_state`: replays (do it for me, reverify) then check the step
against what really happened, with no LLM. Only stable, named things count: a URL, a field's value, a
checkbox, an element with a role and a name that appeared or went. Free text is never used (it changes
between runs).
"""

import re
from collections.abc import Iterable

from app.contracts_gen.common_schema import Action, ElementRef, ExpectedState, FieldValue, Target
from app.ports.models import ObservedState
from app.verifier.aria import AriaNode, parse_aria_snapshot

MAX_VISIBLE = 3
MAX_ABSENT = 2

# Roles that make a good proof, best first: a dialog or a heading says where you are, a status what happened.
_PROOF_ROLES = (
    "dialog", "alertdialog", "heading", "alert", "status", "tab", "listitem", "row", "link", "button",
    "checkbox", "menuitem", "option", "textbox", "searchbox", "combobox", "listbox",
)  # fmt: skip
_CHECKABLE = frozenset({"checkbox", "radio", "switch", "menuitemcheckbox", "menuitemradio"})


def observed_change(
    before: ObservedState, after: ObservedState, action: Action, target: Target | None
) -> ExpectedState | None:
    """The expected state a replay of this step must reach, from what changed. None if nothing visibly did."""
    old, new = parse_aria_snapshot(before.aria_excerpt), parse_aria_snapshot(after.aria_excerpt)
    expected = ExpectedState(
        url_matches=_url(before, after),
        field_values=_fields(action, target, new),
        checked=_checked(action, target, old, new),
        visible=_appeared(old, new) or None,
        absent=_gone(old, new) or None,
    )
    return expected if expected.model_dump(exclude_none=True) else None


def _shown(state: ObservedState) -> str:
    return f"{state.url}?{state.query}" if state.query else state.url


def _url(before: ObservedState, after: ObservedState) -> str | None:
    """The new address, anchored. The query counts only when the path stayed the same (a search on the same
    page): a new page's query often holds volatile parts such as a session or a timestamp."""
    if after.url != before.url:
        return f"^{_path_regex(before.url, after.url)}$"
    if after.query != before.query and after.query:
        return f"^{re.escape(_shown(after))}$"
    return None


_NUMBER = re.compile(r"\d+")
_TOKEN = re.compile(r"(?=[A-Za-z0-9_]*\d)(?=[A-Za-z0-9_]*[A-Za-z])[A-Za-z0-9_]{6,}")
"""An ID a site made up: letters and digits mixed, 6 or more (Trello's board ff6N6zDd)."""
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
"""A UUID, hyphens and all (MusicBrainz's /release-group/b1392450-e666-3926-a536-22c65f834433, #482)."""


def _path_regex(before: str, after: str) -> str:
    """The new path, escaped, with what the site makes up per run left open (#482): a replay that creates
    something gets a new ID, so the recorded one can't be required. Trello opened /b/ff6N6zDd/reading-list
    after "Create"; its replay made /b/W9yq3rpz/reading-list-r606.

    - A segment that is new on this page (not the same segment of the page before) and looks like an ID, all
      digits or `_TOKEN`, may be any ID. Segments that didn't change stay exact, like the docs' /3/.
    - After such an ID, a slug with a hyphen (the item's name, reading-list) may be any slug."""
    old = before.split("/")
    parts, after_id = [], False
    for i, segment in enumerate(after.split("/")):
        new = i >= len(old) or old[i] != segment
        if new and _NUMBER.fullmatch(segment):
            parts.append(r"\d+")
            after_id = True
        elif new and (_TOKEN.fullmatch(segment) or _UUID.fullmatch(segment)):
            parts.append(r"[^/]+")
            after_id = True
        elif new and after_id and "-" in segment and "." not in segment:
            parts.append(r"[^/]+")
        else:
            parts.append(re.escape(segment))
    return "/".join(parts)


def _fields(action: Action, target: Target | None, new: list[AriaNode]) -> list[FieldValue] | None:
    if action.type not in ("fill", "select") or target is None or not target.role or not target.name:
        return None
    for node in new:
        if node.role == target.role and node.name == target.name and node.value == (action.value or ""):
            return [FieldValue(role=node.role, name=node.name, value=node.value)]
    return None


def _checked(
    action: Action, target: Target | None, old: list[AriaNode], new: list[AriaNode]
) -> list[ElementRef] | None:
    if target is None or target.role not in _CHECKABLE or not target.name:
        return None
    was = any(n.role == target.role and n.name == target.name and n.checked for n in old)
    now = any(n.role == target.role and n.name == target.name and n.checked for n in new)
    return [ElementRef(role=target.role, name=target.name)] if now and not was else None


def _named(nodes: Iterable[AriaNode]) -> dict[tuple[str, str], AriaNode]:
    out: dict[tuple[str, str], AriaNode] = {}
    for n in nodes:
        name = n.label().strip()
        if n.role in _PROOF_ROLES and name and len(name) <= 80 and (n.role, name) not in out:
            out[(n.role, name)] = n
    return out


def _ranked(keys: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(keys, key=lambda k: _PROOF_ROLES.index(k[0]))


def _appeared(old: list[AriaNode], new: list[AriaNode]) -> list[ElementRef]:
    before, after = _named(old), _named(new)
    # A field counts too: keys are role + name, so only a field that wasn't on the page before is new (MDN's
    # search dialog opens a combobox "Search").
    fresh = _ranked(k for k in after if k not in before)
    return [ElementRef(role=r, name=n) for r, n in fresh[:MAX_VISIBLE]]


def _gone(old: list[AriaNode], new: list[AriaNode]) -> list[ElementRef]:
    before, after = _named(old), _named(new)
    lost = _ranked(k for k in before if k not in after)
    return [ElementRef(role=r, name=n) for r, n in lost[:MAX_ABSENT]]

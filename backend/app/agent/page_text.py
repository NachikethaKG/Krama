"""Fit a page's ARIA snapshot into a budget before it goes to an LLM (#461).

Real pages ran from 440 to 352,000 characters in the Phase 7 spike (#457); the end-of-run task check once sent
114,688 tokens for one Wikipedia article. What an agent needs most is what it can act on and where it is:
interactive elements, headings and landmarks. Long text matters least. Trimming goes in steps, each only if
the snapshot is still over the budget:

1. shorten very long lines;
2. drop `/url:` lines (a link's address; its name stays);
3. keep only lines with an interactive role, a heading or a landmark, plus their parents (the outline);
4. cut at the budget, on a line boundary, with a marker saying how much was left out.
"""

import re

PAGE_BUDGET_CHARS = 24_000
"""About 6k tokens: room for the prompt around it, even in a local model's 8k context (ADR 0010)."""

MAX_LINE_CHARS = 200

_KEEP_ROLES = frozenset(
    {
        # what can be acted on
        "button", "link", "textbox", "searchbox", "combobox", "checkbox", "radio", "switch", "slider",
        "spinbutton", "menuitem", "menuitemcheckbox", "menuitemradio", "tab", "option", "listbox", "menu",
        "menubar", "tablist", "tree", "treeitem", "grid", "gridcell", "row", "columnheader", "rowheader",
        # where things are
        "heading", "banner", "navigation", "main", "search", "form", "dialog", "alertdialog", "alert",
        "status", "region", "complementary", "contentinfo", "toolbar", "table",
    }
)  # fmt: skip
_ROLE = re.compile(r"^(\s*)- ([a-z]+)\b")
_URL = re.compile(r"^\s*- /url:")


def trim_snapshot(snapshot: str, budget: int = PAGE_BUDGET_CHARS) -> str:
    """The snapshot itself if it fits, else a trimmed copy of at most about `budget` characters."""
    if len(snapshot) <= budget:
        return snapshot
    lines = [_shorten(line) for line in snapshot.splitlines()]
    if _size(lines) > budget:
        lines = [line for line in lines if not _URL.match(line)]
    if _size(lines) > budget:
        lines = _outline(lines)
    if _size(lines) > budget:
        lines = _cut(lines, budget)
    return "\n".join(lines)


def _shorten(line: str) -> str:
    return line if len(line) <= MAX_LINE_CHARS else line[: MAX_LINE_CHARS - 1] + "…"


def _size(lines: list[str]) -> int:
    return sum(len(line) + 1 for line in lines)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _outline(lines: list[str]) -> list[str]:
    """Lines with a kept role, plus every parent of one (by indentation), in page order."""
    keep = [False] * len(lines)
    parents: list[int] = []  # indexes of the open ancestors of the current line
    for i, line in enumerate(lines):
        indent = _indent(line)
        while parents and _indent(lines[parents[-1]]) >= indent:
            parents.pop()
        m = _ROLE.match(line)
        if m and m.group(2) in _KEEP_ROLES:
            keep[i] = True
            for p in parents:
                keep[p] = True
        parents.append(i)
    return [line for line, k in zip(lines, keep, strict=True) if k]


def _cut(lines: list[str], budget: int) -> list[str]:
    out: list[str] = []
    used = 0
    for i, line in enumerate(lines):
        if used + len(line) + 1 > budget - 60:
            return [*out, f"- text: [page cut here: {len(lines) - i} more lines]"]
        out.append(line)
        used += len(line) + 1
    return out

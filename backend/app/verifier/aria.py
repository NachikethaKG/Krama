"""Read Playwright's `aria_snapshot()` YAML into flat nodes, e.g.

- textbox "Repository Name *": demo-repo
- checkbox "Initialize Repository (Adds .gitignore, License and README)" [checked]
- heading "demo-repo" [level=1]
- paragraph: The repository name is already used.
"""

import re
from dataclasses import dataclass, field

_LINE = re.compile(
    r"^\s*- (?P<role>[a-z][a-z0-9-]*)"
    r'(?: "(?P<name>(?:[^"\\]|\\.)*)")?'
    r"(?P<attrs>(?: \[[^\]]*\])*)"
    r"(?::\s?(?P<value>.*))?$"
)
_ATTR = re.compile(r"\[([^\]=]+)(?:=([^\]]*))?\]")


@dataclass(frozen=True)
class AriaNode:
    role: str
    name: str = ""
    value: str = ""
    """Text after the colon: a field's current value, or the text of a text-only node like `paragraph`."""
    attrs: dict[str, str] = field(default_factory=dict)

    @property
    def checked(self) -> bool:
        return self.attrs.get("checked") in ("", "true")

    def label(self) -> str:
        """What a human would read as this element's name: the accessible name, else its text."""
        return self.name or self.value


def parse_aria_snapshot(snapshot: str) -> list[AriaNode]:
    """Every element line of the snapshot, in order. Property lines (`/url:`, `/placeholder:`) are skipped."""
    nodes: list[AriaNode] = []
    for line in snapshot.splitlines():
        m = _LINE.match(line)
        if m is None:
            continue
        name = (m.group("name") or "").replace('\\"', '"')
        value = (m.group("value") or "").strip()
        attrs = {k.strip(): (v or "").strip() for k, v in _ATTR.findall(m.group("attrs") or "")}
        nodes.append(AriaNode(role=m.group("role"), name=name, value=value, attrs=attrs))
    return nodes

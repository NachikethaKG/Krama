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


_QUOTED_KEY = re.compile(r"^(?P<head>\s*- )'(?P<key>(?:[^']|'')*)'(?P<rest>:.*)?$")
"""`- 'combobox "Color: #714802"': "#714802"`: a name with ": " in it makes YAML quote the whole key."""
_FIELDS = frozenset({"textbox", "searchbox", "combobox", "spinbutton"})
_CHILD_TEXT = re.compile(r"^(?P<indent>\s*)- text: (?P<value>.*)$")
_PROPERTY = re.compile(r"^\s*- /")


def parse_aria_snapshot(snapshot: str) -> list[AriaNode]:
    """Every element line of the snapshot, in order. Property lines (`/url:`, `/placeholder:`) are skipped.

    A field's value is usually inline (`- textbox "Title": abc`), but when it needs YAML quoting Playwright
    may write it on a deeper line instead (`- textbox "Add a title":` + `  - text: "Bug: fix login"`, seen on
    GitHub, #89), after property lines like `  - /placeholder: Title`. Both forms give the field its value,
    unquoted."""
    nodes: list[AriaNode] = []
    lines = snapshot.splitlines()
    for i, line in enumerate(lines):
        quoted = _QUOTED_KEY.match(line)
        if quoted is not None:
            line = quoted["head"] + quoted["key"].replace("''", "'") + (quoted["rest"] or "")
        m = _LINE.match(line)
        if m is None:
            continue
        role = m.group("role")
        name = (m.group("name") or "").replace('\\"', '"')
        value = _unquote((m.group("value") or "").strip())
        if role in _FIELDS and not value:
            value = _child_text(lines, i + 1, len(line) - len(line.lstrip()))
        attrs = {k.strip(): (v or "").strip() for k, v in _ATTR.findall(m.group("attrs") or "")}
        nodes.append(AriaNode(role=role, name=name, value=value, attrs=attrs))
    return nodes


def _child_text(lines: list[str], start: int, indent: int) -> str:
    """The first deeper `- text:` line under a field, past property lines like `- /placeholder: Title`."""
    for line in lines[start:]:
        if len(line) - len(line.lstrip()) <= indent:
            break
        child = _CHILD_TEXT.match(line)
        if child is not None:
            return _unquote(child["value"].strip())
        if _PROPERTY.match(line) is None:
            break
    return ""


def _unquote(value: str) -> str:
    """A YAML-quoted scalar ("#d73a4a", 'a: b') as its plain text."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
    return value

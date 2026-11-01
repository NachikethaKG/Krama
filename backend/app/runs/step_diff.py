"""How a workflow version's steps differ from its parent's: the contract's `StepDiff` (workflow.schema.json).

docs/research/phase-4-vishwas-semantic-step-diff.md: align the steps by what they do (action, role, name,
value) with an LCS, pair the leftovers by similarity, then list the changed definition fields. Wording,
geometry and verification evidence differ on every run, so they never make a step "changed" on their own,
except the instruction text, reported as a `wording` change the UI may collapse.
"""

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

from app.contracts_gen.workflow_schema import StepDiff
from app.db import WorkflowStepRow

# Definition fields, most important first: the first one that changed names the step's category.
_FIELDS: list[tuple[str, str]] = [
    ("action", "behaviour"),
    ("target.role", "behaviour"),
    ("target.name", "behaviour"),
    ("target.selector", "behaviour"),
    ("expected_state", "check"),
    ("risk", "risk"),
    ("instruction_text", "wording"),
]
_PAIR_AT = 0.6


def step_diff(
    old: Sequence[WorkflowStepRow], new: Sequence[WorkflowStepRow], *, old_rev: int, new_rev: int
) -> StepDiff:
    old_steps = sorted(old, key=lambda s: s.seq)
    new_steps = sorted(new, key=lambda s: s.seq)
    matcher = SequenceMatcher(
        None, [_key(s) for s in old_steps], [_key(s) for s in new_steps], autojunk=False
    )
    changes: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            changes += [_pair(a, b) for a, b in zip(old_steps[i1:i2], new_steps[j1:j2], strict=True)]
            continue
        left, right = list(old_steps[i1:i2]), list(new_steps[j1:j2])
        while left and right:
            similarity, a, b = max(
                ((_similarity(a, b), a, b) for a in left for b in right), key=lambda t: t[0]
            )
            if similarity < _PAIR_AT:
                break
            changes.append(_pair(a, b))
            left.remove(a)
            right.remove(b)
        changes += [
            {"kind": "removed", "old_seq": a.seq, "category": "behaviour", "summary": _summary(a)}
            for a in left
        ]
        changes += [
            {"kind": "added", "new_seq": b.seq, "category": "behaviour", "summary": _summary(b)}
            for b in right
        ]
    changes.sort(key=lambda c: (c.get("new_seq") or c.get("old_seq") or 0, c.get("new_seq") is None))
    return StepDiff.model_validate({"from_revision": old_rev, "to_revision": new_rev, "steps": changes})


def _get(step: WorkflowStepRow, field: str) -> Any:
    head, _, rest = field.partition(".")
    value = getattr(step, head)
    return (value or {}).get(rest) if rest else value


def _norm(text: str | None) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _key(step: WorkflowStepRow) -> tuple[Any, ...]:
    target, action = step.target or {}, step.action or {}
    return (action.get("type"), target.get("role"), _norm(target.get("name")), action.get("value"))


def _similarity(a: WorkflowStepRow, b: WorkflowStepRow) -> float:
    if (a.action or {}).get("type") != (b.action or {}).get("type"):
        return 0.0
    ta, tb = a.target or {}, b.target or {}
    role = 1.0 if ta.get("role") == tb.get("role") else 0.0
    name = SequenceMatcher(None, _norm(ta.get("name")), _norm(tb.get("name"))).ratio()
    text = SequenceMatcher(None, _norm(a.instruction_text), _norm(b.instruction_text)).ratio()
    expected = 1.0 if a.expected_state == b.expected_state else 0.0
    return 0.3 * role + 0.3 * name + 0.2 * text + 0.2 * expected


def _pair(a: WorkflowStepRow, b: WorkflowStepRow) -> dict[str, Any]:
    fields = [(f, cat, _get(a, f), _get(b, f)) for f, cat in _FIELDS]
    changed = [(f, cat, x, y) for f, cat, x, y in fields if x != y]
    if not changed:
        return {"kind": "same", "old_seq": a.seq, "new_seq": b.seq}
    return {
        "kind": "changed",
        "old_seq": a.seq,
        "new_seq": b.seq,
        "category": changed[0][1],
        "fields": [{"field": f, "from": x, "to": y} for f, _cat, x, y in changed],
    }


def _summary(step: WorkflowStepRow) -> str:
    target, action = step.target or {}, step.action or {}
    what = " ".join(p for p in (action.get("type"), target.get("role")) if p)
    name = target.get("name") or (action.get("value") if action.get("type") == "navigate" else None)
    return f"{what} “{name}”" if name else what

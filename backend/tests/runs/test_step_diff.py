"""The step diff a new version stores as its change_summary (#112; phase-4-vishwas-semantic-step-diff.md)."""

from typing import Any

from app.db import WorkflowStepRow
from app.runs.step_diff import step_diff


def row(seq: int, action: str, role: str | None, name: str | None, text: str, **kw: Any) -> WorkflowStepRow:
    return WorkflowStepRow(
        seq=seq,
        action={"type": action, **({"value": kw.pop("value")} if "value" in kw else {})},
        target={"role": role, "name": name, "bbox": kw.pop("bbox", None)} if role else {},
        instruction_text=text,
        expected_state=kw.pop("expected", {"url_matches": "^/x$"}),
        observed_state={},
        verification={"result": "verified", "method": ["url"], "confidence": 1.0},
        risk="low",
    )


V1 = [
    row(1, "navigate", None, None, "Open the new repository page.", value="/repo/create"),
    row(2, "fill", "textbox", "Repository Name *", "Enter “demo” in “Repository Name”.", value="demo"),
    row(3, "click", "button", "Create Repository", "Click “Create Repository”.", bbox=[1, 2, 3, 4]),
]


def test_a_healed_rename_is_one_changed_behaviour_step_with_its_wording() -> None:
    v2 = [*V1[:2], row(3, "click", "button", "Make repo", "Click “Make repo”.", bbox=[9, 9, 9, 9])]

    diff = step_diff(V1, v2, old_rev=1, new_rev=2)

    assert (diff.from_revision, diff.to_revision) == (1, 2)
    assert [(s.kind, s.old_seq, s.new_seq) for s in diff.steps] == [
        ("same", 1, 1),
        ("same", 2, 2),
        ("changed", 3, 3),
    ]
    changed = diff.steps[2]
    assert changed.category == "behaviour"
    assert [(f.field, f.from_, f.to) for f in changed.fields or []] == [
        ("target.name", "Create Repository", "Make repo"),
        ("instruction_text", "Click “Create Repository”.", "Click “Make repo”."),
    ]


def test_an_inserted_step_shifts_no_other_step() -> None:
    confirm = row(4, "click", "button", "Confirm", "Click “Confirm”.")
    v2 = [*V1, confirm]

    diff = step_diff(V1, v2, old_rev=1, new_rev=2)

    assert [s.kind for s in diff.steps] == ["same", "same", "same", "added"]
    assert diff.steps[3].summary == "click button “Confirm”" and diff.steps[3].new_seq == 4


def test_evidence_and_geometry_alone_change_nothing() -> None:
    v2 = [
        *V1[:2],
        row(3, "click", "button", "Create Repository", "Click “Create Repository”.", bbox=[5, 5, 5, 5]),
    ]

    assert [s.kind for s in step_diff(V1, v2, old_rev=1, new_rev=2).steps] == ["same"] * 3


def test_a_reworded_step_is_a_wording_change() -> None:
    v2 = [
        V1[0],
        row(2, "fill", "textbox", "Repository Name *", "Type “demo” as the name.", value="demo"),
        V1[2],
    ]

    [_, changed, _] = step_diff(V1, v2, old_rev=1, new_rev=2).steps

    assert (changed.kind, changed.category) == ("changed", "wording")

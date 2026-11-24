"""Site notes from earlier verified tutorials (#480): built by code, no values, capped."""

from app.db import WorkflowStepRow
from app.planner.prompt import build_prompt
from app.runs.site_notes import MAX_LINES, notes_from_steps


def row(
    page: str, action: str, role: str | None, name: str | None, value: str | None = None
) -> WorkflowStepRow:
    target = {"role": role, "name": name} if role else {}
    act = {"type": action, **({"value": value} if value else {})}
    return WorkflowStepRow(
        action=act, target=target, before_state={"url": page}, observed_state={"url": page}
    )


def test_pages_and_elements_most_used_first_without_values() -> None:
    notes = notes_from_steps(
        [
            row("/", "click", "link", "New item"),
            row("/form", "fill", "textbox", "Item name *", "my private value"),
            row("/form", "click", "button", "Create item"),
            row("/form", "fill", "textbox", "Item name *", "another value"),
            row("/done", "navigate", None, None, "/done"),
        ]
    )

    assert notes is not None
    lines = notes.splitlines()
    assert lines[1] == '/form: textbox "Item name *" (fill), button "Create item" (click)'
    assert lines[2] == '/: link "New item" (click)'
    assert "private value" not in notes and "another value" not in notes
    assert "/done" not in notes  # a navigate step names no element


def test_no_steps_no_notes_and_the_length_is_capped() -> None:
    assert notes_from_steps([]) is None
    many = [row(f"/page-{i}", "click", "button", f"Button {i}") for i in range(200)]
    notes = notes_from_steps(many)
    assert notes is not None and len(notes.splitlines()) <= MAX_LINES + 1


def test_notes_reach_the_prompt_as_untrusted_data() -> None:
    prompt = build_prompt(
        "t", start_path="/", page_snapshot="- main", site_notes='/form: button "Go" (click)'
    )
    assert '<site_notes untrusted="true">' in prompt and '/form: button "Go" (click)' in prompt

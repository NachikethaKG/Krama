"""\"Do it for me\" inputs (#400): finding them in stored steps, checking values, substituting them."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.agent.runlog import MASK
from app.contracts_gen.workflow_schema import WorkflowInputList
from app.db import WorkflowStepRow
from app.runs.inputs import (
    DoItRefusedError,
    InputUnsafeError,
    check_eligible,
    check_values,
    do_it_steps,
    find_inputs,
    substitute,
)

FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
WORKFLOW = json.loads((FIXTURES / "gitea-create-repo-workflow.json").read_text(encoding="utf-8"))
INPUTS = json.loads((FIXTURES / "workflow-inputs" / "gitea-create-repo-inputs.json").read_text("utf-8"))


def rows(steps: list[dict[str, Any]] | None = None) -> list[WorkflowStepRow]:
    return [
        WorkflowStepRow(
            seq=s["seq"],
            action=s["action"],
            target={k: v for k, v in s["target"].items() if k in ("role", "name", "selector")},
            instruction_text=s["instruction_text"],
            expected_state=s["expected_state"],
            observed_state=s.get("observed_state") or {},
            verification={},
            risk=s.get("risk", "low"),
            sensitive=s.get("sensitive", False),
        )
        for s in (steps if steps is not None else WORKFLOW["steps"])
    ]


def step(seq: int, action: dict[str, Any], name: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "seq": seq,
        "action": action,
        "target": {"role": "textbox", "name": name},
        "instruction_text": extra.pop("text", "Do it."),
        "expected_state": extra.pop("expected", {}),
        **extra,
    }


# --- finding inputs


def test_the_fixture_has_one_input_typed_in_step_3_and_checked_in_step_5() -> None:
    inputs = find_inputs(rows())

    assert [i.model_dump() for i in inputs] == INPUTS["inputs"]  # the contract fixture is what the code says


def test_the_contract_fixture_is_a_valid_input_list() -> None:
    WorkflowInputList.model_validate(INPUTS)


def test_one_input_per_distinct_value_and_unique_keys() -> None:
    steps = [
        step(1, {"type": "fill", "value": "alpha-1"}, "Branch name"),
        step(2, {"type": "fill", "value": "alpha-1"}, "Branch name"),
        step(3, {"type": "fill", "value": "beta-2"}, "Branch name *"),
    ]

    inputs = find_inputs(rows(steps))

    assert [(i.key, i.label, i.example, i.steps) for i in inputs] == [
        ("branch_name", "Branch name", "alpha-1", [1, 2]),
        ("branch_name_2", "Branch name", "beta-2", [3]),
    ]


@pytest.mark.parametrize(
    "action",
    [
        {"type": "select", "value": "MIT"},  # dropdowns replay the recorded option (P15)
        {"type": "fill", "value": "line one\nline two"},  # multi-line text
        {"type": "fill", "value": "one two three four five six seven eight nine"},  # a body, not a name
        {"type": "fill", "value": MASK},
        {"type": "fill", "value": "  "},
        {"type": "click", "value": None},
    ],
)
def test_values_that_are_not_inputs(action: dict[str, Any]) -> None:
    assert find_inputs(rows([step(1, action, "Field")])) == []


def test_a_sensitive_fill_is_never_an_input() -> None:
    password = step(1, {"type": "fill", "value": "hunter22"}, "Password", sensitive=True)

    assert find_inputs(rows([password])) == []


def test_a_field_without_a_label_gets_a_step_key() -> None:
    [only] = find_inputs(rows([step(4, {"type": "fill", "value": "notes-9"}, None)]))

    assert (only.key, only.label) == ("step_4_value", "Value for step 4")


@pytest.mark.parametrize(
    ("example", "pattern"),
    [
        ("demo-repo-4821", "^[A-Za-z0-9._-]+$"),
        ("v1.2_rc", "^[A-Za-z0-9._-]+$"),
        ("bug+fix", "^[A-Za-z0-9\\+._-]+$"),
        ("Fix the login bug", None),  # free text: any single line
        ("café", None),  # non-ASCII letters: no simple class
    ],
)
def test_the_pattern_is_the_examples_character_class(example: str, pattern: str | None) -> None:
    [only] = find_inputs(rows([step(1, {"type": "fill", "value": example}, "Title")]))

    assert only.pattern == pattern
    if pattern is not None:
        assert re.fullmatch(pattern, example)


# --- checking values


def test_good_values_map_from_their_example() -> None:
    assert check_values(find_inputs(rows()), {"repository_name": "team-notes"}) == {"demo-repo": "team-notes"}


@pytest.mark.parametrize(
    ("values", "key"),
    [
        ({}, "repository_name"),  # missing
        ({"repository_name": "team-notes", "owner": "x"}, "owner"),  # unknown
        ({"repository_name": "ab"}, "repository_name"),  # shorter than 3
        ({"repository_name": "team notes"}, "repository_name"),  # a space the example didn't have
        ({"repository_name": "team/notes"}, "repository_name"),
        ({"repository_name": " team-notes"}, "repository_name"),
        ({"repository_name": "team\nnotes"}, "repository_name"),
    ],
)
def test_unsafe_values_are_refused(values: dict[str, str], key: str) -> None:
    with pytest.raises(InputUnsafeError) as e:
        check_values(find_inputs(rows()), values)

    assert e.value.key == key


# --- substituting


def test_the_value_is_replaced_in_every_place_it_reappears() -> None:
    planned = do_it_steps(rows(), {"repository_name": "team-notes"})
    by_seq = {p["seq"]: p for p in planned}

    assert by_seq[3]["action"]["value"] == "team-notes"
    assert by_seq[3]["expected_state"]["field_values"][0]["value"] == "team-notes"
    assert by_seq[3]["instruction_text"] == "Enter team-notes as the repository name."
    assert by_seq[5]["expected_state"]["url_matches"] == "^/demo/team\\-notes$"
    assert re.search(by_seq[5]["expected_state"]["url_matches"], "/demo/team-notes")
    assert by_seq[5]["expected_state"]["title_contains"] == "demo/team-notes"
    assert by_seq[5]["expected_state"]["visible"] == [{"role": "heading", "name": "team-notes"}]
    assert "demo-repo" not in json.dumps(planned)


def test_a_value_with_a_dot_is_escaped_in_the_url_check() -> None:
    planned = do_it_steps(rows(), {"repository_name": "team.notes"})

    url = planned[4]["expected_state"]["url_matches"]
    assert re.search(url, "/demo/team.notes")
    assert not re.search(url, "/demo/teamXnotes")


def test_an_escaped_example_in_a_url_check_is_found_too() -> None:
    planned = [{"seq": 1, "expected_state": {"url_matches": "^/demo/v1\\.2$"}}]

    assert substitute(planned, {"v1.2": "v2.0"})[0]["expected_state"]["url_matches"] == "^/demo/v2\\.0$"


def test_only_whole_tokens_are_replaced() -> None:
    planned = [{"seq": 1, "instruction_text": "Open main, not maintenance or domain."}]

    swapped = substitute(planned, {"main": "dev"})

    assert swapped[0]["instruction_text"] == "Open dev, not maintenance or domain."


def test_a_derived_name_is_replaced_too() -> None:
    planned = [{"seq": 1, "target": {"role": "link", "name": "demo-repo-settings"}}]

    assert substitute(planned, {"demo-repo": "team"})[0]["target"]["name"] == "team-settings"


def test_values_are_swapped_in_one_pass() -> None:
    planned = [{"seq": 1, "instruction_text": "Copy alpha-1 to beta-2."}]

    swapped = substitute(planned, {"alpha-1": "beta-2", "beta-2": "gamma-3"})

    assert swapped[0]["instruction_text"] == "Copy beta-2 to gamma-3."


def test_substitute_never_changes_the_stored_steps() -> None:
    stored = rows()
    before = json.dumps([s.expected_state for s in stored])

    do_it_steps(stored, {"repository_name": "team-notes"})

    assert json.dumps([s.expected_state for s in stored]) == before


# --- eligibility


def test_a_verified_workflow_with_a_high_risk_step_is_eligible() -> None:
    steps = rows()
    steps[4].risk = "high"  # it pauses for confirmation during the run (P2)

    check_eligible("verified", steps, pending_review=False)


@pytest.mark.parametrize(
    ("status", "pending", "change", "reason"),
    [
        ("outdated", False, None, "not_verified"),
        ("verified", True, None, "pending_review"),
        ("verified", False, "sensitive", "secret_not_stored"),
        ("verified", False, "masked", "secret_not_stored"),
    ],
)
def test_ineligible_workflows_are_refused(
    status: str, pending: bool, change: str | None, reason: str
) -> None:
    steps = rows()
    if change == "sensitive":
        steps[2].sensitive = True
    if change == "masked":
        steps[2].action = {"type": "fill", "value": MASK}

    with pytest.raises(DoItRefusedError) as e:
        check_eligible(status, steps, pending_review=pending)

    assert e.value.reason == reason
    if change:
        assert e.value.step_seq == 3

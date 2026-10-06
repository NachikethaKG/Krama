"""Contract tests for Verified Workflow and Step schemas (contracts/schemas/{workflow,step}.schema.json)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts_gen.events_schema import RunEvent
from app.contracts_gen.step_schema import Step, StepVerification
from app.contracts_gen.workflow_schema import Workflow

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = ROOT / "contracts" / "schemas"
FIXTURES_DIR = ROOT / "contracts" / "fixtures"


def test_schema_files_are_valid_and_reference_step() -> None:
    step_schema_path = SCHEMAS_DIR / "step.schema.json"
    workflow_schema_path = SCHEMAS_DIR / "workflow.schema.json"

    assert step_schema_path.exists(), "step.schema.json must exist"
    assert workflow_schema_path.exists(), "workflow.schema.json must exist"

    step_schema = json.loads(step_schema_path.read_text(encoding="utf-8"))
    workflow_schema = json.loads(workflow_schema_path.read_text(encoding="utf-8"))

    assert step_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert step_schema["$id"] == "step.schema.json"
    assert step_schema["title"] == "Step"
    assert "VerificationResult" in step_schema["$defs"]
    assert step_schema["$defs"]["VerificationResult"]["enum"] == ["verified", "failed", "skipped"]

    assert workflow_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert workflow_schema["$id"] == "workflow.schema.json"
    assert workflow_schema["title"] == "Workflow"
    assert "WorkflowStatus" in workflow_schema["$defs"]
    assert workflow_schema["$defs"]["WorkflowStatus"]["enum"] == [
        "draft",
        "approved",
        "running",
        "verified",
        "failed",
        "outdated",
    ]

    # Verify $ref relationship
    steps_ref = workflow_schema["properties"]["steps"]["items"]["$ref"]
    assert steps_ref == "step.schema.json", "Workflow.steps must reference step.schema.json via $ref"


def test_valid_workflow_fixture_parses_successfully() -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    assert fixture_path.exists(), "valid_workflow.json fixture must exist"

    raw_data = json.loads(fixture_path.read_text(encoding="utf-8"))
    workflow = Workflow.model_validate(raw_data)

    assert isinstance(workflow.id, UUID)
    assert workflow.title == "Create a repository in Gitea"
    assert workflow.status == "verified"
    assert workflow.confidence == 0.98
    assert workflow.target is not None
    assert workflow.target.app == "gitea"
    assert len(workflow.steps) == 2

    step1 = workflow.steps[0]
    assert isinstance(step1, Step)
    assert step1.seq == 1
    assert step1.action.type == "click"
    assert step1.target.name == "Create…"
    assert step1.target.bbox == (1146, 6, 56, 36)
    assert step1.verification.result == "verified"
    assert step1.verification.confidence == 1.0
    assert step1.risk == "low"
    assert step1.timing is not None
    assert step1.timing.start_ms == 2718
    assert step1.timing.end_ms == 3047


def test_individual_step_parsing_and_enums() -> None:
    step_data = {
        "id": "11111111-1111-4111-8111-111111111111",
        "seq": 1,
        "action": {"type": "select", "value": "main"},
        "target": {"role": "combobox", "name": "Branch"},
        "instruction_text": "Select the main branch.",
        "expected_state": {"visible": [{"role": "option", "name": "main"}]},
        "observed_state": {"url": "/repo/branch"},
        "verification": {"result": "skipped", "method": ["dom"], "confidence": 0.5},
        "risk": "medium",
    }
    step = Step.model_validate(step_data)
    assert step.action.type == "select"
    assert step.verification.result == "skipped"
    assert step.risk == "medium"


@pytest.mark.parametrize("bad_status", ["unknown", "complete", "pending", "VERIFIED"])
def test_invalid_workflow_status_enum_rejected(bad_status: str) -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data["status"] = bad_status
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


@pytest.mark.parametrize("bad_action", ["hover", "double_click", "drag", "scroll"])
def test_invalid_action_type_enum_rejected(bad_action: str) -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data["steps"][0]["action"]["type"] = bad_action
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


@pytest.mark.parametrize("bad_result", ["passed", "error", "ok", "fail"])
def test_invalid_verification_result_enum_rejected(bad_result: str) -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data["steps"][0]["verification"]["result"] = bad_result
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


@pytest.mark.parametrize("bad_risk", ["critical", "none", "extreme", "LOW"])
def test_invalid_risk_enum_rejected(bad_risk: str) -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data["steps"][0]["risk"] = bad_risk
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


@pytest.mark.parametrize("missing_field", ["id", "title", "status", "steps"])
def test_workflow_missing_required_field_rejected(missing_field: str) -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    del data[missing_field]
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


@pytest.mark.parametrize(
    "missing_step_field",
    [
        "id",
        "seq",
        "action",
        "target",
        "instruction_text",
        "expected_state",
        "observed_state",
        "verification",
        "risk",
    ],
)
def test_step_missing_required_field_rejected(missing_step_field: str) -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    del data["steps"][0][missing_step_field]
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


def test_closed_objects_reject_unknown_fields() -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data["unexpected_property"] = "disallowed"
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


@pytest.mark.parametrize("bad_confidence", [-0.1, 1.01, 2.0])
def test_confidence_bounds_enforced(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        StepVerification(result="verified", method=["url"], confidence=bad_confidence)


def test_bounding_box_rejects_wrong_length() -> None:
    fixture_path = FIXTURES_DIR / "valid_workflow.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    data["steps"][0]["target"]["bbox"] = [10, 20, 30]  # needs 4 elements
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


def test_gitea_create_repo_workflow_fixture_validates() -> None:
    fixture_path = FIXTURES_DIR / "gitea-create-repo-workflow.json"
    assert fixture_path.exists(), "gitea-create-repo-workflow.json fixture must exist"

    raw_data = json.loads(fixture_path.read_text(encoding="utf-8"))
    workflow = Workflow.model_validate(raw_data)

    assert workflow.title == "Create a repository in local Gitea"
    assert workflow.status == "verified"
    assert workflow.confidence == 1.0
    assert workflow.target is not None
    assert workflow.target.app == "gitea"
    assert workflow.preconditions == {"logged_in_as": "demo"}
    assert workflow.viewport is not None
    assert workflow.viewport.width == 1280
    assert workflow.viewport.height == 800
    assert len(workflow.steps) == 5

    expected_actions = ["click", "click", "fill", "click", "click"]
    for i, step in enumerate(workflow.steps):
        assert step.seq == i + 1
        assert step.action.type == expected_actions[i]
        assert step.verification.result == "verified"
        assert step.verification.confidence == 1.0
        assert step.risk == "low"
        assert step.target.bbox is not None
        assert len(step.target.bbox) == 4
        if step.screenshot_path:
            screenshot_file = ROOT / step.screenshot_path
            assert screenshot_file.exists(), f"Screenshot {screenshot_file} must exist"


def test_gitea_create_repo_sse_events_fixture_validates() -> None:
    fixture_path = FIXTURES_DIR / "gitea-create-repo-events.sse"
    assert fixture_path.exists(), "gitea-create-repo-events.sse fixture must exist"

    raw_text = fixture_path.read_text(encoding="utf-8")
    blocks = [b.strip() for b in raw_text.strip().split("\n\n") if b.strip()]
    assert len(blocks) == 17, f"Expected 17 SSE event blocks, got {len(blocks)}"

    adapter: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)
    parsed_events: list[RunEvent] = []

    for block in blocks:
        lines = block.splitlines()
        event_type = None
        event_id = None
        data_str = None
        for line in lines:
            if line.startswith("event: "):
                event_type = line[len("event: ") :].strip()
            elif line.startswith("id: "):
                event_id = int(line[len("id: ") :].strip())
            elif line.startswith("data: "):
                data_str = line[len("data: ") :].strip()

        assert event_type is not None, f"Block missing 'event:': {block}"
        assert event_id is not None, f"Block missing 'id:': {block}"
        assert data_str is not None, f"Block missing 'data:': {block}"

        data = json.loads(data_str)
        assert data["type"] == event_type
        assert data["seq"] == event_id

        event_obj = adapter.validate_python(data)
        parsed_events.append(event_obj)

    assert parsed_events[0].type == "run.started"
    assert parsed_events[0].total_steps == 5
    assert parsed_events[-1].type == "run.completed"
    assert parsed_events[-1].verified_steps == 5
    assert parsed_events[-1].failed_actions == 0

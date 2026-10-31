from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.models import WorkflowRow, WorkflowStepRow
from app.db.repositories import add_workflow_version


@pytest.mark.anyio
async def test_add_workflow_version_deterministic_auto_promotes():
    workflow_id = uuid4()
    v1_id = uuid4()
    workflow = WorkflowRow(
        id=workflow_id,
        title="Test Workflow",
        target_app="gitea",
        target_url="http://localhost:3001",
        status="outdated",
        revision=1,
        current_version_id=v1_id,
        confidence=1.0,
    )

    step = WorkflowStepRow(
        seq=1,
        action={"type": "click"},
        target={"role": "button", "name": "Create repository"},
        instruction_text="Click Create repository",
        expected_state={},
        observed_state={},
        verification={},
        risk="low",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get.return_value = workflow
    mock_session.scalar.return_value = 1  # max revision is 1

    added_objects = []

    def mock_add(obj):
        added_objects.append(obj)

    mock_session.add.side_effect = mock_add

    version = await add_workflow_version(
        mock_session,
        workflow_id=workflow_id,
        source="heal",
        status="current",
        steps=[step],
        change_summary={"changes": [{"seq": 1, "kind": "changed"}]},
    )

    assert version.workflow_id == workflow_id
    assert version.revision == 2
    assert version.source == "heal"
    assert version.status == "current"
    assert version.parent_version_id == v1_id
    assert workflow.current_version_id == version.id
    assert workflow.revision == 2
    assert workflow.status == "verified"


@pytest.mark.anyio
async def test_add_workflow_version_pending_review_keeps_workflow_outdated():
    workflow_id = uuid4()
    v1_id = uuid4()
    workflow = WorkflowRow(
        id=workflow_id,
        title="Test Workflow",
        target_app="gitea",
        target_url="http://localhost:3001",
        status="outdated",
        revision=1,
        current_version_id=v1_id,
        confidence=1.0,
    )

    step = WorkflowStepRow(
        seq=1,
        action={"type": "click"},
        target={"role": "button", "name": "Create repository"},
        instruction_text="Click Create repository",
        expected_state={},
        observed_state={},
        verification={},
        risk="low",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get.return_value = workflow
    mock_session.scalar.return_value = 1

    version = await add_workflow_version(
        mock_session,
        workflow_id=workflow_id,
        source="heal",
        status="pending_review",
        steps=[step],
        change_summary={"changes": [{"seq": 1, "kind": "changed"}]},
    )

    assert version.workflow_id == workflow_id
    assert version.revision == 2
    assert version.status == "pending_review"
    # Workflow should remain outdated per D8
    assert workflow.status == "outdated"
    # Current version pointer should NOT change when pending review
    assert workflow.current_version_id == v1_id

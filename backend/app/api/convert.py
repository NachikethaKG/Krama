"""Database rows → contract models (contracts/schemas). Routes return only these, never rows."""

import base64
import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from app.api.errors import ApiException
from app.contracts_gen.export_schema import Export
from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.run_schema import Run
from app.contracts_gen.step_schema import Step
from app.contracts_gen.task_schema import Task
from app.contracts_gen.workflow_schema import Workflow, WorkflowSummary, WorkflowVersion
from app.db import ExportRow, PlanRow, RunRow, TaskRow, WorkflowRow, WorkflowStepRow, WorkflowVersionRow


def task_out(row: TaskRow, plan_id: UUID | None) -> Task:
    return Task.model_validate(
        {
            "id": row.id,
            "prompt": row.prompt,
            "target_url": row.target_url,
            "status": row.status,
            "interpretation": row.interpretation,
            "clarification_question": row.clarification_question,
            "plan_id": plan_id,
            "regenerates_workflow_id": row.regenerates_workflow_id,
            "error": row.error,
            "created_at": row.created_at,
        }
    )


def plan_out(row: PlanRow) -> Plan:
    return Plan.model_validate(
        {
            "id": row.id,
            "task_id": row.task_id,
            "revision": row.revision,
            "status": row.status,
            "risk": row.risk,
            "expected_result": row.expected_result,
            "steps": row.steps,
            "created_at": row.created_at,
            "approved_at": row.approved_at,
        }
    )


def run_out(row: RunRow, workflow_id: UUID | None) -> Run:
    return Run.model_validate(
        {
            "id": row.id,
            "plan_id": row.plan_id,
            "plan_revision": row.plan_revision,
            "kind": row.kind,
            "source_workflow_id": row.source_workflow_id,
            "status": row.status,
            "current_seq": row.current_seq,
            "retry_count": row.retry_count,
            "workflow_id": workflow_id,
            "error": row.error,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
    )


_INTERNAL_TARGET_KEYS = frozenset({"fingerprint"})
"""Stored with a step's target for self-healing (#112), not part of the contract's StepTarget."""


def workflow_out(row: WorkflowRow, task_prompt: str | None) -> Workflow:
    return _workflow(row, task_prompt, _steps_out(row.id, row.steps))


def workflow_version_out(
    row: WorkflowRow, version: WorkflowVersionRow, steps: Sequence[WorkflowStepRow], task_prompt: str | None
) -> Workflow:
    """The workflow as it was at `version`: its steps, recording, viewport, confidence and revision.
    An export renders the version it was asked for, even if a newer one became current since."""
    return _workflow(
        row,
        task_prompt,
        _steps_out(row.id, steps),
        revision=version.revision,
        confidence=version.confidence,
        recording_path=version.recording_path,
        viewport=version.viewport,
    )


def _steps_out(workflow_id: UUID, rows: Sequence[WorkflowStepRow]) -> list[Step]:
    return [
        Step.model_validate(
            {
                "id": st.id,
                "workflow_id": workflow_id,
                "seq": st.seq,
                "action": st.action,
                "target": {k: v for k, v in (st.target or {}).items() if k not in _INTERNAL_TARGET_KEYS},
                "instruction_text": st.instruction_text,
                "before_state": st.before_state,
                "expected_state": st.expected_state,
                "observed_state": st.observed_state,
                "verification": st.verification,
                "risk": st.risk,
                "sensitive": st.sensitive,
                "screenshot_path": st.screenshot_path,
                "start_ms": st.start_ms,
                "end_ms": st.end_ms,
            }
        )
        for st in rows
    ]


def _workflow(row: WorkflowRow, task_prompt: str | None, steps: list[Step], **version: Any) -> Workflow:
    """`version`: revision, confidence, recording_path, viewport of a version other than the current one."""
    return Workflow.model_validate(
        {
            "id": row.id,
            "revision": row.revision,  # the contract's `version` is the format version
            "task_id": row.task_id,
            "run_id": row.run_id,
            "title": row.title,
            "task": task_prompt,
            "target": {"app": row.target_app, "base_url": row.target_url},
            "target_app": row.target_app,
            "target_url": row.target_url,
            "status": row.status,
            "confidence": row.confidence,
            "preconditions": row.preconditions,
            "viewport": row.viewport,
            "recording_path": row.recording_path,
            "steps": steps,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            **version,
        }
    )


def workflow_summary(row: WorkflowRow) -> WorkflowSummary:
    return WorkflowSummary.model_validate(
        {
            "id": row.id,
            "title": row.title,
            "status": row.status,
            "target_app": row.target_app,
            "step_count": len(row.steps),
            "confidence": row.confidence,
            "created_at": row.created_at,
        }
    )


def version_out(row: WorkflowVersionRow, step_count: int) -> WorkflowVersion:
    return WorkflowVersion.model_validate(
        {
            "id": row.id,
            "workflow_id": row.workflow_id,
            "revision": row.revision,
            "source": row.source,
            "status": row.status,
            "parent_version_id": row.parent_version_id,
            "run_id": row.run_id,
            "confidence": row.confidence,
            "step_count": step_count,
            "change_summary": row.change_summary,
            "created_at": row.created_at,
        }
    )


def export_out(row: ExportRow, *, title: str | None, revision: int) -> Export:
    """`title` and `revision` come from the workflow and the exported version."""
    ready = row.status == "ready"
    base = f"/api/v1/exports/{row.id}"
    error = (
        {"code": row.error_code, "message": row.error_message or ""}
        if row.status == "failed" and row.error_code
        else None
    )
    return Export.model_validate(
        {
            "id": row.id,
            "workflow_id": row.workflow_id,
            "revision": revision,
            "title": title,
            "preset": row.preset,
            "voice": row.voice,
            "status": row.status,
            "progress": row.progress,
            "size_bytes": row.size_bytes,
            "duration_ms": row.duration_ms,
            "download_url": f"{base}/download" if ready else None,
            "captions_url": f"{base}/captions.vtt" if ready and row.captions_key else None,
            "error": error,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
    )


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    """Opaque keyset cursor: the (created_at, id) of the last item on the page."""
    raw = json.dumps([created_at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if cursor is None:
        return None
    try:
        raw: Any = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return datetime.fromisoformat(raw[0]), UUID(raw[1])
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise ApiException(422, "validation_error", "Invalid cursor") from e

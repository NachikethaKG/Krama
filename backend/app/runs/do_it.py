"""\"Do it for me\" runs (#129, #401): a stored verified workflow run for its owner with their own values.

Like a reverify (#77), the stored steps become an approved plan that the normal executor runs, but a do-it
run acts for the user: it never resets the site (P8), it pauses at risky steps instead of failing (P6), and it
stores no workflow (P9). Decisions in docs/research/phase-6-decisions-alignment.md.
"""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts_gen.workflow_schema import WorkflowInputList
from app.db import PlanRow, RunRow, WorkflowRow, WorkflowVersionRow
from app.runs.inputs import DoItRefusedError, check_eligible, do_it_steps, find_inputs
from app.runs.reverify import plan_risk


async def _eligible(s: AsyncSession, workflow: WorkflowRow) -> None:
    pending = await s.scalar(
        select(WorkflowVersionRow.id)
        .where(WorkflowVersionRow.workflow_id == workflow.id, WorkflowVersionRow.status == "pending_review")
        .limit(1)
    )
    check_eligible(workflow.status, list(workflow.steps), pending_review=pending is not None)


async def workflow_inputs(
    s: AsyncSession, workflow: WorkflowRow, account: str | None, sign_in_site: str | None = None
) -> WorkflowInputList:
    """GET /workflows/{id}/inputs. Raises DoItRefusedError for a workflow that can't run for the user."""
    await _eligible(s, workflow)
    return WorkflowInputList(
        workflow_id=workflow.id,
        revision=workflow.revision,
        inputs=find_inputs(list(workflow.steps)),
        account=account,
        sign_in_site=sign_in_site,
    )


_NAME = r"A-Za-z0-9._\-"


def swap_account(planned: list[dict[str, Any]], recorded: str, account: str) -> list[dict[str, Any]]:
    """The recording account replaced by the user's (ADR 0007), only where it is a path segment: `/demo/x`,
    `^/demo/x$`, `demo/x` in a title. "demo-repo" keeps its name."""
    if not recorded or recorded == account:
        return planned
    old = re.escape(recorded)
    path = re.compile(rf"(?<![{_NAME}]){old}(?=/)|(?<=/){old}(?![{_NAME}])")
    escaped = re.compile(rf"(?<![{_NAME}\\]){re.escape(old)}(?=/)|(?<=/){re.escape(old)}(?![{_NAME}])")

    def fix(value: Any, regex: bool = False) -> Any:
        if isinstance(value, str):
            value = path.sub(account, value)
            return escaped.sub(re.escape(account), value) if regex else value
        if isinstance(value, list):
            return [fix(v) for v in value]
        if isinstance(value, dict):
            return {k: fix(v, regex=k == "url_matches") for k, v in value.items()}
        return value

    return [fix(step) for step in planned]


async def create_do_it_run(
    sessions: async_sessionmaker[AsyncSession],
    workflow_id: UUID,
    revision: int,
    values: Mapping[str, str],
    *,
    account: tuple[str | None, str] | None = None,
) -> UUID:
    """Store the approved plan (the current steps with the user's values) and a queued `do_it` run.

    Raises LookupError for an unknown workflow, DoItRefusedError (`not_verified`, `pending_review`,
    `secret_not_stored`, `stale_revision`) and InputUnsafeError for a value that can't be used."""
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        if workflow is None:
            raise LookupError(str(workflow_id))
        await _eligible(s, workflow)
        if revision != workflow.revision:
            raise DoItRefusedError(
                "stale_revision",
                f"The workflow changed: version {workflow.revision} is current, not {revision}",
            )
        steps = list(workflow.steps)
        planned = do_it_steps(steps, values)
        if account is not None:  # (the shared account that recorded it, the user's own)
            current = workflow.current_version
            recorded = (current.recorded_as if current is not None else None) or account[0]
            planned = swap_account(planned, recorded or "", account[1])
        plan = PlanRow(
            task_id=workflow.task_id,
            status="approved",
            risk=plan_risk(steps),
            expected_result=workflow.title,
            steps=planned,
            approved_at=datetime.now(UTC),  # starting it is the approval (P6)
        )
        s.add(plan)
        await s.flush()
        run = RunRow(
            plan_id=plan.id, plan_revision=1, status="queued", kind="do_it", source_workflow_id=workflow_id
        )
        s.add(run)
        await s.flush()
        return run.id

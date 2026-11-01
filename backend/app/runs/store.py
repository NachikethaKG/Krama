"""Run persistence for the executor: one short transaction per transition or event, never a request's
session.

Every write goes through app.db.repositories, which validates each event against the contract and writes it
in the same transaction as the run's status change.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts_gen.plan_schema import PlannedStep
from app.db import PlanRow, RunRow, TaskRow, WorkflowRow, WorkflowStepRow
from app.db.repositories import (
    add_workflow,
    add_workflow_version,
    append_event,
    decide_plan,
    runs_with_status,
    transition_run,
)
from app.runs.states import ACTIVE, RunStatus, event_type, sources
from app.runs.step_diff import step_diff


@dataclass(frozen=True)
class RunJob:
    """Everything the executor needs to run one approved plan."""

    run_id: UUID
    task_id: UUID
    plan_id: UUID
    prompt: str
    target_url: str
    status: RunStatus
    steps: list[PlannedStep]
    plan_revision: int = 1
    """The approved revision. Above 1, a human edited the plan, so their step texts are kept as written."""
    kind: str = "task"
    """task, or reverify: a replay of `source_workflow_id`'s stored steps that stores no workflow (#77)."""
    source_workflow_id: UUID | None = None


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


class RunNotFoundError(LookupError):
    pass


class _NotRunningError(Exception):
    pass


type OnEvent = Callable[[UUID], Awaitable[None]]


class RunStore:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, on_event: OnEvent | None = None
    ) -> None:
        """`on_event(run_id)` runs after every committed event (it wakes the live-view streams)."""
        self._sessions = sessions
        self._on_event = on_event

    async def _committed(self, run_id: UUID, wrote: bool) -> bool:
        if wrote and self._on_event is not None:
            await self._on_event(run_id)
        return wrote

    async def load(self, run_id: UUID) -> RunJob:
        async with self._sessions() as s:
            run = await s.get(RunRow, run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            plan = await s.get(PlanRow, run.plan_id)
            task = await s.get(TaskRow, plan.task_id) if plan else None
            if plan is None or task is None:
                raise RunNotFoundError(run_id)
            return RunJob(
                run_id=run.id,
                task_id=task.id,
                plan_id=plan.id,
                prompt=task.prompt,
                target_url=task.target_url,
                status=RunStatus(run.status),
                steps=[PlannedStep.model_validate(step) for step in plan.steps],
                plan_revision=run.plan_revision,
                kind=run.kind,
                source_workflow_id=run.source_workflow_id,
            )

    async def status(self, run_id: UUID) -> RunStatus:
        async with self._sessions() as s:
            run = await s.get(RunRow, run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            return RunStatus(run.status)

    async def transition(
        self,
        run_id: UUID,
        to: RunStatus,
        event_data: Mapping[str, Any],
        *,
        from_: RunStatus | None = None,
        **changes: Any,
    ) -> bool:
        """Move the run to `to` and record its event. False if the run wasn't in an allowed status.

        With `from_`, only that source status is accepted (and it picks run.started vs run.resumed).
        Without it, any status the table allows.
        """
        if from_ is None and to is RunStatus.RUNNING:
            raise ValueError("moving to running needs from_ (run.started and run.resumed differ)")
        allowed = {from_} if from_ is not None else sources(to)
        kind = event_type(from_ if from_ is not None else next(iter(sources(to))), to)
        if to not in ACTIVE:
            changes.setdefault("finished_at", datetime.now(UTC))
        async with self._sessions.begin() as s:
            row = await transition_run(
                s, run_id, to=to, allowed_from=allowed, event_type=kind, event_data=event_data, **changes
            )
        return await self._committed(run_id, row is not None)

    async def cancel(self, run_id: UUID, reason: str) -> bool:
        """Cancel a queued, running or paused run. The event names the step it was on, read under the same
        row lock as the transition. False if the run had already finished (or doesn't exist)."""
        async with self._sessions.begin() as s:
            current = await s.scalar(select(RunRow.current_seq).where(RunRow.id == run_id).with_for_update())
            data: dict[str, Any] = {"reason": reason}
            if current is not None:
                data["step_seq"] = current
            row = await transition_run(
                s,
                run_id,
                to=RunStatus.CANCELLED,
                allowed_from=sources(RunStatus.CANCELLED),
                event_type="run.cancelled",
                event_data=data,
                finished_at=datetime.now(UTC),
            )
        return await self._committed(run_id, row is not None)

    async def fail(
        self,
        run_id: UUID,
        *,
        from_: RunStatus,
        message: str,
        reason: str,
        code: str = "internal",
        **details: Any,
    ) -> bool:
        """End the run as failed. `reason` (e.g. step_not_verified) goes in error.details, because the
        contract's ErrorCode has no run-specific codes yet."""
        error = {"code": code, "message": message, "details": {"reason": reason, **details}}
        return await self.transition(run_id, RunStatus.FAILED, {"error": error}, from_=from_, error=error)

    async def event(self, run_id: UUID, kind: str, data: Mapping[str, Any], **changes: Any) -> bool:
        """A step event, written only while the run is still running. False once it was cancelled."""
        async with self._sessions.begin() as s:
            row = await append_event(s, run_id, kind, data, while_status=(RunStatus.RUNNING,), **changes)
        return await self._committed(run_id, row is not None)

    async def complete(
        self,
        job: RunJob,
        steps: Sequence[WorkflowStepRow],
        *,
        confidence: float,
        recording_path: str | None = None,
        viewport: dict[str, Any] | None = None,
        **changes: Any,
    ) -> UUID | None:
        """Store the verified workflow and finish the run, in ONE transaction: a workflow exists only for a
        run that completed. None if the run was no longer running (e.g. cancelled at the last moment)."""
        try:
            async with self._sessions.begin() as s:
                workflow = WorkflowRow(
                    task_id=job.task_id,
                    run_id=job.run_id,
                    user_id=await s.scalar(select(TaskRow.user_id).where(TaskRow.id == job.task_id)),
                    title=job.prompt,
                    target_app=_app_of(job.target_url),
                    target_url=job.target_url,
                    status="verified",
                    confidence=confidence,
                    recording_path=recording_path,
                    viewport=viewport,
                )
                workflow_id = await self._complete(s, job, workflow, steps, **changes)
        except _NotRunningError:
            return None  # the transaction rolled back, workflow included
        await self._committed(job.run_id, True)
        return workflow_id

    async def complete_reverify(self, job: RunJob, *, verified_steps: int, **changes: Any) -> bool:
        """End a reverify run as verified. No workflow is stored; run.completed names the re-verified one."""
        assert job.source_workflow_id is not None
        async with self._sessions.begin() as s:
            row = await transition_run(
                s,
                job.run_id,
                to=RunStatus.VERIFIED,
                allowed_from=(RunStatus.RUNNING,),
                event_type="run.completed",
                event_data={
                    "workflow_id": str(job.source_workflow_id),
                    "verified_steps": verified_steps,
                    "failed_actions": 0,
                },
                finished_at=datetime.now(UTC),
                **changes,
            )
        return await self._committed(job.run_id, row is not None)

    async def stored_targets(self, workflow_id: UUID) -> dict[int, dict[str, Any]]:
        """The current version's stored targets (with their fingerprints, #112), by step seq."""
        async with self._sessions() as s:
            workflow = await s.get(WorkflowRow, workflow_id)
            return {st.seq: dict(st.target or {}) for st in (workflow.steps if workflow else [])}

    async def complete_heal(
        self,
        job: RunJob,
        rows: Sequence[WorkflowStepRow],
        *,
        needs_review: bool,
        confidence: float,
        recording_path: str | None,
        viewport: dict[str, Any] | None,
        **changes: Any,
    ) -> UUID | None:
        """End a reverify run that healed a step (#112) as verified, and store what it ran as the next version
        of the workflow, in ONE transaction. `needs_review` (a Gemini heal, D8): the version waits for a human
        and the workflow is outdated meanwhile; otherwise it is current at once. None if the run was no longer
        running."""
        assert job.source_workflow_id is not None
        try:
            async with self._sessions.begin() as s:
                workflow = await s.get(WorkflowRow, job.source_workflow_id, with_for_update=True)
                if workflow is None:
                    raise _NotRunningError  # deleted meanwhile: nothing to add a version to
                parent, parent_revision = list(workflow.steps), workflow.revision
                version = await add_workflow_version(
                    s,
                    workflow,
                    rows,
                    source="heal",
                    status="pending_review" if needs_review else "current",
                    run_id=job.run_id,
                    confidence=confidence,
                    recording_path=recording_path,
                    viewport=viewport,
                    change_summary=None,
                )
                diff = step_diff(parent, rows, old_rev=parent_revision, new_rev=version.revision)
                version.change_summary = diff.model_dump(mode="json", by_alias=True, exclude_none=True)
                row = await transition_run(
                    s,
                    job.run_id,
                    to=RunStatus.VERIFIED,
                    allowed_from=(RunStatus.RUNNING,),
                    event_type="run.completed",
                    event_data={
                        "workflow_id": str(workflow.id),
                        "verified_steps": len(rows),
                        "failed_actions": 0,
                    },
                    finished_at=datetime.now(UTC),
                    **changes,
                )
                if row is None:
                    raise _NotRunningError
                version_id = version.id
        except _NotRunningError:
            return None
        await self._committed(job.run_id, True)
        return version_id

    async def _complete(
        self,
        s: AsyncSession,
        job: RunJob,
        workflow: WorkflowRow,
        steps: Sequence[WorkflowStepRow],
        **changes: Any,
    ) -> UUID:
        await add_workflow(s, workflow, steps)
        row = await transition_run(
            s,
            job.run_id,
            to=RunStatus.VERIFIED,
            allowed_from=(RunStatus.RUNNING,),
            event_type="run.completed",
            event_data={
                "workflow_id": str(workflow.id),
                "verified_steps": len(steps),
                "failed_actions": 0,
            },
            finished_at=datetime.now(UTC),
            **changes,
        )
        if row is None:
            raise _NotRunningError
        return workflow.id

    async def propose_plan(self, job: RunJob, steps: Sequence[PlannedStep], *, expected_result: str) -> UUID:
        """Store replanned steps as a new proposed plan of the same task (the human reviews it)."""
        risk = max((s.risk for s in steps), key=_RISK_ORDER.__getitem__, default="low")
        async with self._sessions.begin() as s:
            plan = PlanRow(
                task_id=job.task_id,
                status="proposed",
                risk=risk,
                expected_result=expected_result,
                steps=[step.model_dump(mode="json", exclude_none=True) for step in steps],
            )
            s.add(plan)
            await s.flush()
            return plan.id

    async def adopt_plan(self, run_id: UUID, plan_id: UUID) -> None:
        """The human allowed the replanned steps: approve that plan and run it from now on."""
        async with self._sessions.begin() as s:
            plan = await decide_plan(s, plan_id, revision=1, to="approved")
            if plan is None:
                raise RunNotFoundError(plan_id)
            run = await s.get(RunRow, run_id, with_for_update=True)
            if run is None:
                raise RunNotFoundError(run_id)
            run.plan_id, run.plan_revision = plan_id, plan.revision

    async def unfinished(self) -> Sequence[UUID]:
        """Runs a restart interrupted: queued, running or paused, with no browser behind them any more."""
        async with self._sessions() as s:
            return await runs_with_status(s, (RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.PAUSED))

    async def current_step(self, run_id: UUID) -> tuple[RunStatus, int | None]:
        async with self._sessions() as s:
            run = await s.get(RunRow, run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            return RunStatus(run.status), run.current_seq


def _app_of(target_url: str) -> str:
    # Phase 1 only targets the local Gitea; Phase 3 adds GitHub and a real mapping.
    return "github" if "github.com" in target_url else "gitea"

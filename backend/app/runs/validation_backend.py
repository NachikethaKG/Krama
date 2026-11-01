"""The run engine's side of scheduled validation (#110): the `ValidationBackend` port.

Validation (`app.validation`) decides which workflow to re-check and what the result means; this module lists
the stored workflows, replays one as a reverify run (healing included, #112) and stores the verdict.
"""

from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import RunRow, ValidationRow, WorkflowRow, WorkflowVersionRow
from app.db.repositories import event_payload, events_after
from app.ports.validation import ReplayOutcome, StepEvidence, ValidationRecord, WorkflowCandidate
from app.runs.executor import ARTIFACTS_URL, InProcessExecutor
from app.runs.reverify import ReverifyRefusedError, create_reverify_run
from app.targets import TargetSetup

REPLAYABLE_APPS = ("gitea", "github")
_RECENT = 5


class RunValidationBackend:
    """`ValidationBackend` on the database and an `InProcessExecutor` (the worker's: one browser)."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        executor: InProcessExecutor,
        target: Callable[[str], TargetSetup],
    ) -> None:
        self._sessions = sessions
        self._executor = executor
        self._target = target

    async def candidates(self) -> list[WorkflowCandidate]:
        async with self._sessions() as s:
            workflows = (
                await s.scalars(select(WorkflowRow).where(WorkflowRow.target_app.in_(REPLAYABLE_APPS)))
            ).all()
            out = []
            for w in workflows:
                recent = (
                    await s.execute(
                        select(ValidationRow.status, ValidationRow.ran_at)
                        .where(ValidationRow.workflow_id == w.id)
                        .order_by(ValidationRow.ran_at.desc())
                        .limit(_RECENT)
                    )
                ).all()
                out.append(
                    WorkflowCandidate(
                        workflow_id=w.id,
                        site=urlsplit(w.target_url).netloc,
                        target_app=w.target_app,
                        status=w.status,
                        revision=w.revision,
                        last_validated_at=recent[0].ran_at if recent else None,
                        recent=tuple(r.status for r in recent),
                    )
                )
        # Never checked first, then the longest unchecked.
        return sorted(out, key=lambda c: (c.last_validated_at is not None, c.last_validated_at or 0))

    async def replay(self, workflow_id: UUID) -> ReplayOutcome:
        async with self._sessions() as s:
            workflow = await s.get(WorkflowRow, workflow_id)
            if workflow is None:
                raise LookupError(str(workflow_id))
            version_id, target_url = workflow.current_version_id, workflow.target_url
            stored = {st.seq: st for st in workflow.steps}
        try:
            run_id = await create_reverify_run(self._sessions, workflow_id, self._target(target_url).reset)
        except ReverifyRefusedError as e:
            return ReplayOutcome(
                result="refused", version_id=version_id, reason=e.reason, step_seq=e.step_seq
            )
        await self._executor.submit(run_id)
        await self._executor.wait(run_id)
        async with self._sessions() as s:
            run = await s.get(RunRow, run_id)
            assert run is not None
            events = [event_payload(e) for e in await events_after(s, run_id)]
            new_version = await s.scalar(
                select(WorkflowVersionRow.status).where(WorkflowVersionRow.run_id == run_id)
            )
        if run.status == "verified":
            return ReplayOutcome(
                result="verified",
                run_id=run_id,
                version_id=version_id,
                new_version=new_version if new_version in ("current", "pending_review") else None,
                steps=_evidence(stored, events),
            )
        details: dict[str, Any] = dict(((run.error or {}).get("details")) or {})
        reason = details.get("reason") or run.status  # a cancelled run has no error
        if reason == "policy_stop":
            reason = details.get("policy_reason") or reason  # captcha, auth_wall, rate_limited, ...
        return ReplayOutcome(
            result="failed",
            run_id=run_id,
            version_id=version_id,
            reason=str(reason),
            step_seq=details.get("step_seq"),
            details=details,
            steps=_evidence(stored, events),
        )

    async def record(self, record: ValidationRecord) -> None:
        async with self._sessions.begin() as s:
            s.add(
                ValidationRow(
                    workflow_id=record.workflow_id,
                    version_id=record.version_id,
                    run_id=record.run_id,
                    status=record.status,
                    drift_details=record.drift_details,
                )
            )
            workflow = await s.get(WorkflowRow, record.workflow_id, with_for_update=True)
            if workflow is None:
                return
            if record.status == "outdated":
                workflow.status = "outdated"
            elif record.status == "passed" and workflow.status == "outdated":
                waiting = await s.scalar(
                    select(WorkflowVersionRow.id).where(
                        WorkflowVersionRow.workflow_id == workflow.id,
                        WorkflowVersionRow.status == "pending_review",
                    )
                )
                if waiting is None:
                    workflow.status = "verified"  # the site works again with the current version


def _evidence(stored: dict[int, Any], events: list[dict[str, Any]]) -> tuple[StepEvidence, ...]:
    """Each replayed step's screenshot and box (its last `step.action_done`: a healed step has two), next to
    the stored step's."""
    done: dict[int, dict[str, Any]] = {}
    for e in events:
        if e.get("type") == "step.action_done":
            done[int(e["step_seq"])] = e
    out = []
    for seq in sorted(done):
        step, event = stored.get(seq), done[seq]
        bbox = (step.target or {}).get("bbox") if step is not None else None
        out.append(
            StepEvidence(
                seq=seq,
                stored_screenshot=step.screenshot_path if step is not None else None,
                new_screenshot=_key(event.get("screenshot_url")),
                stored_bbox=tuple(bbox) if isinstance(bbox, list) and len(bbox) == 4 else None,
                new_bbox=tuple(event["bbox"]) if isinstance(event.get("bbox"), list) else None,
            )
        )
    return tuple(out)


def _key(url: Any) -> str | None:
    """`/api/v1/artifacts/<key>` -> `<key>`."""
    prefix = f"{ARTIFACTS_URL}/"
    return url[len(prefix) :] if isinstance(url, str) and url.startswith(prefix) else None

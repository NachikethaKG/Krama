"""In-process run executor (Phases 0-2): runs approved plans as asyncio tasks in the API process.

Phase 3 swaps this for an arq worker behind the same `RunExecutor` interface (docs/architecture.md §4).
Every status change and event goes through RunStore, one transaction each, so the database always holds
the truth. A crash leaves the run at its last committed status, and `recover()` fails it on the next start.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import UUID

from playwright.async_api import Page

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig
from app.agent.runlog import MASK, ScriptedStep, looks_sensitive, mask_expected, run_script
from app.agent.vision import VisionLocator
from app.contracts_gen.events_schema import PauseReason
from app.contracts_gen.plan_schema import PlannedStep
from app.db import WorkflowStepRow
from app.db.base import literal_values
from app.ports.models import ObservedState, PageState, PolicyDecision
from app.ports.observer import Observer
from app.ports.policy import Policy
from app.runs.states import RunStatus
from app.runs.steps import StepOutcome, act_and_verify, step_ref
from app.runs.store import RunJob, RunNotFoundError, RunStore
from app.verifier import StepVerifier

logger = logging.getLogger(__name__)

ARTIFACTS_URL = "/api/v1/artifacts"
# The pause reasons the contract knows. A policy pause with any other reason stops the run instead (#216 adds
# sensitive_data and prompt_injection; they become pauses by themselves once the contract is regenerated).
PAUSE_REASONS = frozenset(literal_values(PauseReason))

type Decision = Literal["allow", "deny"]


class RunExecutor(Protocol):
    async def submit(self, run_id: UUID) -> None:
        """Start a queued run in the background. Returns at once."""
        ...

    async def cancel(self, run_id: UUID) -> bool:
        """Cancel a queued, running or paused run. False if it had already finished."""
        ...

    async def confirm(self, run_id: UUID, step_seq: int, decision: Decision) -> bool:
        """Answer a run paused at `step_seq`. False if it isn't paused there."""
        ...


@dataclass
class RunEnvironment:
    """What a run needs besides its plan. Built once by the composition root (app startup, tests)."""

    verifier: StepVerifier
    observer_for: Callable[[UUID], Observer]
    """The Observer for one run (the composition root picks the concrete one behind the port)."""
    artifacts_dir: Path
    """Where the observer's files live; paths under it become /api/v1/artifacts/... URLs."""
    preconditions: Callable[[RunJob], Sequence[ScriptedStep]] = lambda _job: ()
    """Setup before step 1, e.g. signing in. Not part of the plan or the recording."""
    session_config: Callable[[RunJob], SessionConfig] = field(
        default=lambda job: SessionConfig(base_url=job.target_url)
    )
    vision: VisionLocator | None = None
    policy: Policy | None = None
    """Asked before every step (allow / pause / stop). None until the real Policy (#61) is wired in; a step
    the approved plan marks high risk pauses either way."""
    verify_timeout_s: float = 5.0
    verify_interval_s: float = 0.25
    pause_timeout_s: float = 1800.0
    """How long a paused run keeps its browser open waiting for /confirm before it gives up."""


class InProcessExecutor:
    """At most `max_concurrent` runs at once (MAX_CONCURRENT_RUNS=1 locally); later ones wait as `queued`."""

    def __init__(self, store: RunStore, env: RunEnvironment, *, max_concurrent: int = 1) -> None:
        self._store = store
        self._env = env
        self._slots = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._answers: dict[UUID, asyncio.Future[None]] = {}
        """Paused runs waiting for /confirm allow."""

    @property
    def artifacts_dir(self) -> Path:
        return self._env.artifacts_dir

    async def submit(self, run_id: UUID) -> None:
        if run_id in self._tasks:
            return
        task = asyncio.create_task(self._guarded(run_id), name=f"run-{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(run_id, None))

    async def cancel(self, run_id: UUID) -> bool:
        if not await self._store.cancel(run_id, reason="user"):
            return False
        await self._stop_task(run_id)
        return True

    async def confirm(self, run_id: UUID, step_seq: int, decision: Decision) -> bool:
        try:
            status, current = await self._store.current_step(run_id)
        except RunNotFoundError:
            return False
        waiting = self._answers.get(run_id)
        if status is not RunStatus.PAUSED or current != step_seq or waiting is None or waiting.done():
            return False
        if decision == "deny":
            if not await self._store.cancel(run_id, reason="confirmation_denied"):
                return False
            await self._stop_task(run_id)
            return True
        resumed = {"step_seq": step_seq, "decision": "allow"}
        if not await self._store.transition(run_id, RunStatus.RUNNING, resumed, from_=RunStatus.PAUSED):
            return False
        waiting.set_result(None)
        return True

    async def _stop_task(self, run_id: UUID) -> None:
        task = self._tasks.get(run_id)
        if task is not None:
            task.cancel()  # the DB already says cancelled; this stops the steps and closes the browser
            await asyncio.wait({task}, timeout=10)  # so the caller sees a run whose browser is gone

    async def wait(self, run_id: UUID) -> None:
        """Wait for a run's task to end (tests, shutdown). Returns at once if it isn't running here."""
        task = self._tasks.get(run_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    async def recover(self) -> list[UUID]:
        """On startup: queued, running and paused runs have no browser any more, so they fail. (A paused
        run can't continue without the page it paused on.) Returns the runs it failed."""
        failed = []
        for run_id in await self._store.unfinished():
            status = await self._store.status(run_id)
            if await self._store.fail(
                run_id, from_=status, message="Interrupted by a server restart", reason="interrupted"
            ):
                failed.append(run_id)
        return failed

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.cancelling():  # a second cancel would interrupt the browser cleanup itself
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _guarded(self, run_id: UUID) -> None:
        async with self._slots:
            try:
                await self._run(run_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("run %s crashed", run_id)
                status = await self._store.status(run_id)
                if status in (RunStatus.QUEUED, RunStatus.RUNNING):
                    await self._store.fail(run_id, from_=status, message="Internal error", reason="crash")

    async def _run(self, run_id: UUID) -> None:
        job = await self._store.load(run_id)
        if job.status is not RunStatus.QUEUED:
            return  # cancelled while waiting for a slot, or submitted twice
        started = {"plan_id": str(job.plan_id), "total_steps": len(job.steps)}
        if not await self._store.transition(
            run_id, RunStatus.RUNNING, started, from_=RunStatus.QUEUED, started_at=datetime.now(UTC)
        ):
            return
        t0 = time.perf_counter()
        env = self._env
        config = env.session_config(job)
        async with PlaywrightSession(config) as session:
            page = session.page
            executor = ActionExecutor(page, vision=env.vision)
            await page.goto("/", wait_until="domcontentloaded")
            setup = list(env.preconditions(job))
            if setup:
                log = await run_script(executor, setup, task="preconditions", base_url=job.target_url)
                if not log.ok:
                    failed = log.failed_entry
                    detail = failed.result.error.code if failed and failed.result.error else "failed"
                    await self._store.fail(
                        run_id, from_=RunStatus.RUNNING, message=f"Precondition failed ({detail})",
                        reason="precondition_failed",
                    )  # fmt: skip
                    return
            observer = env.observer_for(run_id)
            await observer.start_recording(page)
            rows: list[WorkflowStepRow] = []
            try:
                for step in job.steps:
                    row = await self._step(job, step, executor, observer, page)
                    if row is None:
                        return  # failed or cancelled; the store already says so
                    rows.append(row)
            finally:
                recording = await observer.stop_recording()
        await self._store.complete(
            job,
            rows,
            confidence=min((r.verification["confidence"] for r in rows), default=1.0),
            recording_path=self._artifact_key(recording.path),
            viewport={"width": config.viewport_width, "height": config.viewport_height},
            duration_ms=round((time.perf_counter() - t0) * 1000),
        )

    async def _step(
        self, job: RunJob, step: PlannedStep, executor: ActionExecutor, observer: Observer, page: Page
    ) -> WorkflowStepRow | None:
        """Run one step and announce it. The verified step's row, or None if the run must stop."""
        store, seq = self._store, step.seq
        if not await store.event(
            job.run_id, "step.started", {"step_seq": seq, "instruction_text": step.instruction_text},
            current_seq=seq,
        ):  # fmt: skip
            return None  # cancelled meanwhile
        before = await observer.capture(page, step_ref(step))
        if not await self._allowed(job, step, before):
            return None
        out = await act_and_verify(
            step,
            executor,
            observer,
            self._env.verifier,
            page,
            verify_timeout_s=self._env.verify_timeout_s,
            verify_interval_s=self._env.verify_interval_s,
            before=before,
        )
        shot = self._artifact_url(out.observed.screenshot_path)
        bbox = list(out.result.bbox) if out.result.bbox else None
        done = {"step_seq": seq, "screenshot_url": shot, "bbox": bbox}
        if not await store.event(job.run_id, "step.action_done", done):
            return None
        if out.verified and out.verification is not None:
            v = out.verification.verification
            verified = {"step_seq": seq, "method": list(v.method), "confidence": v.confidence}
            if not await store.event(job.run_id, "step.verified", verified):
                return None
            return self._row(step, out)
        failed = {
            "step_seq": seq,
            "expected": mask_expected(step.expected_state).model_dump(mode="json", exclude_none=True),
            "observed": {"url": out.observed.url, "title": out.observed.title},
            "screenshot_url": shot,
        }
        if await store.event(job.run_id, "step.failed", failed):
            if out.unclear:
                # Agreed (#45): an unclear step pauses for a human. Until the contract has a pause reason for
                # it and /confirm can resume (#59), the run stops here instead; it never passes silently.
                reason, why = "verification_unclear", "nothing proved the step worked"
            else:
                reason = "step_not_verified"
                why = out.result.error.code if out.result.error else "expected state not reached"
            await store.fail(
                job.run_id, from_=RunStatus.RUNNING, message=f"Step {seq} did not verify ({why})",
                reason=reason, step_seq=seq,
            )  # fmt: skip
        return None

    async def _allowed(self, job: RunJob, step: PlannedStep, before: ObservedState) -> bool:
        """Ask the policy before acting (AGENTS.md §4). True to go ahead; False if the run stopped."""
        decision = PolicyDecision(verdict="allow")
        if self._env.policy is not None:
            page = PageState(url=before.url, title=before.title, aria_excerpt=before.aria_excerpt)
            decision = await self._env.policy.check_action(step_ref(step), page)
        if decision.verdict == "allow" and step.risk == "high":
            # The approved plan itself says this step is risky: a human confirms it right before it runs.
            message = "The plan marks this step as high risk."
            decision = PolicyDecision(verdict="pause", reason="destructive_action", message=message)
        if decision.verdict == "allow":
            return True
        if decision.verdict == "pause" and decision.reason in PAUSE_REASONS:
            return await self._pause(job, step, decision)
        # A stop, or a pause the contract can't express yet: never continue.
        await self._store.fail(
            job.run_id,
            from_=RunStatus.RUNNING,
            message=decision.message or f"Stopped by the safety policy ({decision.reason})",
            reason="policy_stop",
            policy_reason=decision.reason,
            step_seq=step.seq,
        )
        return False

    async def _pause(self, job: RunJob, step: PlannedStep, decision: PolicyDecision) -> bool:
        """Pause with the browser open until /confirm. True if a human allowed the step."""
        answer: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._answers[job.run_id] = answer
        try:
            paused: dict[str, Any] = {"reason": decision.reason, "step_seq": step.seq}
            if decision.message:
                paused["message"] = decision.message
            if not await self._store.transition(
                job.run_id, RunStatus.PAUSED, paused, from_=RunStatus.RUNNING
            ):
                return False  # cancelled meanwhile
            try:
                await asyncio.wait_for(asyncio.shield(answer), self._env.pause_timeout_s)
            except TimeoutError:
                await self._store.fail(
                    job.run_id,
                    from_=RunStatus.PAUSED,
                    message="Nobody answered the pause in time",
                    reason="pause_timeout",
                    step_seq=step.seq,
                )
                return False
            return True  # confirm() already moved the run back to running
        finally:
            self._answers.pop(job.run_id, None)

    def _row(self, step: PlannedStep, out: StepOutcome) -> WorkflowStepRow:
        """The stored step. Sensitive fill values are masked; the ARIA text stays out (it can hold typed
        values), the screenshot is referenced by its artifact key."""
        sensitive = step.action.value is not None and looks_sensitive(step.target.name)
        action = step.action.model_copy(update={"value": MASK}) if sensitive else step.action
        key = self._artifact_key(out.observed.screenshot_path)
        assert out.verification is not None
        return WorkflowStepRow(
            seq=step.seq,
            action=action.model_dump(mode="json", exclude_none=True),
            target={
                **step.target.model_dump(mode="json", exclude_none=True),
                "bbox": list(out.result.bbox) if out.result.bbox else None,
            },
            instruction_text=step.instruction_text,
            expected_state=mask_expected(step.expected_state).model_dump(mode="json", exclude_none=True),
            before_state=_summary(out.before) if out.before else None,
            observed_state={
                "url": out.observed.url,
                "title": out.observed.title,
                "headings": out.observed.headings,
                "screenshot_path": key,
                "captured_at": out.observed.captured_at.isoformat(),
            },
            verification=out.verification.verification.model_dump(mode="json"),
            risk=step.risk,
            sensitive=sensitive,
            screenshot_path=key,
        )

    def _artifact_key(self, path: str | None) -> str | None:
        """The observer writes files under ARTIFACTS_DIR; the API serves them by their relative key."""
        if not path:
            return None
        try:
            return Path(path).resolve().relative_to(self._env.artifacts_dir.resolve()).as_posix()
        except ValueError:
            return None  # not under the artifacts dir: never expose arbitrary paths

    def _artifact_url(self, path: str | None) -> str | None:
        key = self._artifact_key(path)
        return f"{ARTIFACTS_URL}/{key}" if key else None


def _summary(state: ObservedState) -> dict[str, Any]:
    """What is stored about a page state: no ARIA text (it can hold typed values), no own screenshot."""
    return {
        "url": state.url,
        "title": state.title,
        "headings": state.headings,
        "captured_at": state.captured_at.isoformat(),
    }

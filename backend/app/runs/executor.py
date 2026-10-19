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
from urllib.parse import urlsplit
from uuid import UUID

from playwright.async_api import Page

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig, page_snapshot
from app.agent.runlog import MASK, ScriptedStep, looks_sensitive, mask_expected, run_script
from app.agent.vision import VisionLocator
from app.contracts_gen.events_schema import PauseReason
from app.contracts_gen.plan_schema import PlannedStep
from app.db import WorkflowStepRow
from app.db.base import literal_values
from app.llm import LLMError
from app.planner.instructions import tutorial_text
from app.planner.planner import Planner, PlannerError, PlanRequest
from app.ports.models import (
    InvalidArtifactKeyError,
    ObservedState,
    PageState,
    PolicyDecision,
    validate_artifact_key,
)
from app.ports.observer import Observer
from app.ports.policy import Policy
from app.runs.states import RunStatus
from app.runs.steps import StepOutcome, act_and_verify, step_ref
from app.runs.store import RunJob, RunNotFoundError, RunStore
from app.targets import TargetSetup
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
    planner: Planner | None = None
    """For replanning after a failed step. None: no replans, the run pauses for the human instead."""
    target: Callable[[RunJob], TargetSetup] = lambda _job: TargetSetup()
    """Site hints and sign-in identity for the replan prompt."""
    run_timeout_s: float = 600.0
    """Time a run may spend running (pauses don't count). Then it fails."""
    max_replans_per_run: int = 3


class InProcessExecutor:
    """At most `max_concurrent` runs at once (MAX_CONCURRENT_RUNS=1 locally); later ones wait as `queued`."""

    def __init__(self, store: RunStore, env: RunEnvironment, *, max_concurrent: int = 1) -> None:
        self._store = store
        self._env = env
        self._slots = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._answers: dict[UUID, asyncio.Future[None]] = {}
        """Paused runs waiting for /confirm allow."""
        self._paused_s: dict[UUID, float] = {}
        """Seconds each run spent paused (they don't count toward run_timeout_s)."""

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
            try:
                rows = await self._steps(job, executor, observer, page)
            finally:
                recording = await observer.stop_recording()
        if rows is None:
            return  # failed, paused out or cancelled; the store already says so
        if job.kind == "reverify":
            duration_ms = round((time.perf_counter() - t0) * 1000)
            await self._store.complete_reverify(job, verified_steps=len(rows), duration_ms=duration_ms)
            return
        await self._store.complete(
            job,
            rows,
            confidence=min((r.verification["confidence"] for r in rows), default=1.0),
            recording_path=self._artifact_key(recording.path),
            viewport={
                "width": config.viewport_width,
                "height": config.viewport_height,
                "device_scale_factor": config.device_scale_factor,
            },
            duration_ms=round((time.perf_counter() - t0) * 1000),
        )

    async def _steps(
        self, job: RunJob, executor: ActionExecutor, observer: Observer, page: Page
    ) -> list[WorkflowStepRow] | None:
        """Every step in order, with recovery (docs/research/phase-1-vishwas-agent-recovery.md): retry an
        idempotent step once, else replan the rest (a human re-approves it), else pause for the human.
        The rows of the finished steps, or None if the run stopped."""
        env, store = self._env, self._store
        steps = list(job.steps)
        rows: list[WorkflowStepRow] = []
        budget = _Recovery(max_replans=env.max_replans_per_run)
        self._paused_s[job.run_id] = 0.0
        t0 = time.perf_counter()
        i = 0
        while i < len(steps):
            step = steps[i]
            if time.perf_counter() - t0 - self._paused_s[job.run_id] > env.run_timeout_s:
                await store.fail(
                    job.run_id, from_=RunStatus.RUNNING, reason="run_timeout", step_seq=step.seq,
                    message=f"The run took longer than {env.run_timeout_s:g} s (pauses not counted)",
                )  # fmt: skip
                return None
            out = await self._attempt(job, step, executor, observer, page, budget.retry_count)
            if out is None:
                return None  # stopped by the policy, or cancelled
            if out.verified:
                rows.append(self._row(job, step, out))
                budget.succeeded()
                i += 1
                continue
            if out.unclear:
                message = (
                    "Nothing proved this step worked. Check the page: allow accepts the step, deny cancels."
                )
                if not await self._pause(job, step.seq, "verification_unclear", message):
                    return None
                rows.append(self._row(job, step, out))  # a human accepted it; its confidence stays below 0.8
                budget.succeeded()
                i += 1
                continue

            move, why = budget.after_failure(step, out)
            if move == "retry":
                continue  # same step again; budget.retry_count already counts it
            if job.kind == "reverify":
                await self._fail_reverify(job, step, out)
                return None  # the later steps depend on this one: they are not run
            if move == "replan":
                replanned = await self._replan(job, steps, i, out, page, budget)
                if replanned is not None:
                    new_steps, plan_id = replanned
                    message = "The agent proposes new remaining steps. Allow runs them, deny cancels."
                    if not await self._pause(job, step.seq, "replan_review", message, plan_id=plan_id):
                        return None
                    await store.adopt_plan(job.run_id, plan_id)
                    steps = [*steps[:i], *new_steps]
                    continue
                why = "the replan didn't produce new steps"
            if not await self._pause(
                job,
                step.seq,
                "recovery_exhausted",
                f"Step {step.seq} failed: {why}. Allow tries it once more.",
            ):
                return None
            budget.retry_count += 1  # the human asked for one more try
        return rows

    async def _attempt(
        self,
        job: RunJob,
        step: PlannedStep,
        executor: ActionExecutor,
        observer: Observer,
        page: Page,
        retry_count: int,
    ) -> StepOutcome | None:
        """One try of one step, announced on the live view. None if the run stopped (policy, cancel)."""
        store, seq = self._store, step.seq
        if not await store.event(
            job.run_id, "step.started", {"step_seq": seq, "instruction_text": step.instruction_text},
            current_seq=seq, retry_count=retry_count,
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
        if not await store.event(
            job.run_id, "step.action_done", {"step_seq": seq, "screenshot_url": shot, "bbox": bbox}
        ):
            return None
        if out.verified and out.verification is not None:
            v = out.verification.verification
            verified = {"step_seq": seq, "method": list(v.method), "confidence": v.confidence}
            return out if await store.event(job.run_id, "step.verified", verified) else None
        failed = {
            "step_seq": seq,
            "expected": mask_expected(step.expected_state).model_dump(mode="json", exclude_none=True),
            "observed": {"url": out.observed.url, "title": out.observed.title},
            "screenshot_url": shot,
        }
        return out if await store.event(job.run_id, "step.failed", failed) else None

    async def _replan(
        self,
        job: RunJob,
        steps: list[PlannedStep],
        i: int,
        out: StepOutcome,
        page: Page,
        budget: "_Recovery",
    ) -> tuple[list[PlannedStep], UUID] | None:
        """Ask the planner for new remaining steps after steps[i] failed, and store them as a proposed plan.
        Returns the new steps (numbered from steps[i].seq) and the plan's id, or None."""
        env, failed = self._env, steps[i]
        budget.replans += 1
        budget.retry_count += 1
        reason = f"step {failed.seq} failed: {_failure_reason(out)}"
        if not await self._store.event(
            job.run_id, "run.replanning", {"reason": reason, "attempt": budget.replans},
            retry_count=budget.retry_count,
        ):  # fmt: skip
            return None
        if env.planner is None:
            return None
        setup = env.target(job)
        request = PlanRequest(
            task_id=job.task_id,
            task=job.prompt,
            start_path=self._mask(urlsplit(page.url).path or "/"),
            page_snapshot=await self._masked_snapshot(page),
            site=setup.site,
            signed_in_as=setup.signed_in_as,
            done=[s.instruction_text for s in steps[:i]],
            failure=self._mask(_failure_text(failed, out)),
        )
        try:
            result = await env.planner.plan(request)
        except (PlannerError, LLMError) as e:
            logger.info("replan for run %s failed: %s", job.run_id, e)
            return None
        new_steps = [s.model_copy(update={"seq": failed.seq + k}) for k, s in enumerate(result.plan.steps)]
        plan_id = await self._store.propose_plan(
            job, [*steps[:i], *new_steps], expected_result=result.plan.expected_result
        )
        return new_steps, plan_id

    async def _masked_snapshot(self, page: Page) -> str:
        """The page's ARIA snapshot with secrets masked by the policy (#63) before it goes to an LLM."""
        return self._mask(await page_snapshot(page))

    def _mask(self, text: str) -> str:
        """Page-derived text (snapshot, URL path, failure details) through the policy's mask, before any LLM
        sees it. Tokens can sit in a URL as easily as on the page."""
        if self._env.policy is None:
            return text
        state = ObservedState(url="/", title="", aria_excerpt=text, captured_at=datetime.now(UTC))
        return self._env.policy.mask(state).aria_excerpt

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
            return await self._pause(job, step.seq, decision.reason, decision.message or None)
        # A stop, or a pause the contract can't express: never continue.
        await self._store.fail(
            job.run_id,
            from_=RunStatus.RUNNING,
            message=decision.message or f"Stopped by the safety policy ({decision.reason})",
            reason="policy_stop",
            policy_reason=decision.reason,
            step_seq=step.seq,
        )
        return False

    async def _fail_reverify(self, job: RunJob, step: PlannedStep, out: StepOutcome) -> None:
        """A stored step no longer works. locator_miss: its element is gone or ambiguous (the UI changed);
        action_failed: the action itself failed; state_mismatch: it ran but its expected state didn't hold."""
        error = out.result.error
        if error is not None and error.code in ("target_not_found", "ambiguous_target"):
            reason, what = "locator_miss", f"its element wasn't found ({error.code})"
        elif error is not None:
            reason, what = "action_failed", f"its action failed ({error.code})"
        else:
            reason, what = "state_mismatch", "it ran, but the expected state didn't hold"
        await self._store.fail(
            job.run_id, from_=RunStatus.RUNNING, message=f"Step {step.seq} no longer works: {what}",
            reason=reason, step_seq=step.seq,
        )  # fmt: skip

    async def _pause(
        self,
        job: RunJob,
        step_seq: int,
        reason: str,
        message: str | None = None,
        *,
        plan_id: UUID | None = None,
    ) -> bool:
        """Pause with the browser open until /confirm. True if a human allowed it (deny cancels the task).

        A reverify run has nobody watching it: instead of pausing it fails, with the pause reason."""
        if job.kind == "reverify":
            text = message or f"Step {step_seq} needs a human ({reason})"
            await self._store.fail(
                job.run_id, from_=RunStatus.RUNNING, message=f"Re-verification stopped: {text}",
                reason=reason, step_seq=step_seq,
            )  # fmt: skip
            return False
        answer: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._answers[job.run_id] = answer
        t0 = time.perf_counter()
        try:
            paused: dict[str, Any] = {"reason": reason, "step_seq": step_seq}
            if message:
                paused["message"] = message
            if plan_id is not None:
                paused["plan_id"] = str(plan_id)
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
                    step_seq=step_seq,
                )
                return False
            return True  # confirm() already moved the run back to running
        finally:
            self._answers.pop(job.run_id, None)
            if job.run_id in self._paused_s:
                self._paused_s[job.run_id] += time.perf_counter() - t0

    def _row(self, job: RunJob, step: PlannedStep, out: StepOutcome) -> WorkflowStepRow:
        """The stored step. Sensitive fill values are masked; the ARIA text stays out (it can hold typed
        values), the screenshot is referenced by its artifact key. The step text is rewritten from what ran
        (label, dialog/section, page reached); the plan keeps the text the human approved."""
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
                "scroll": out.result.scroll.model_dump() if out.result.scroll else None,
            },
            instruction_text=self._step_text(job, step, out, sensitive=sensitive),
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

    @staticmethod
    def _step_text(job: RunJob, step: PlannedStep, out: StepOutcome, *, sensitive: bool) -> str:
        """The tutorial text: rewritten from what ran, unless a human edited the plan (their words win)."""
        if job.plan_revision > 1:
            return step.instruction_text
        rewritten = tutorial_text(
            step.action,
            step.target,
            out.result.context,
            page_title=out.before.title if out.before else None,
            sensitive=sensitive,
        )
        return rewritten or step.instruction_text

    def _artifact_key(self, path: str | None) -> str | None:
        """The key the API serves an observer artifact by (`/api/v1/artifacts/<key>`).

        An observer backed by the ArtifactStore (#50) returns keys; one writing to a folder returns file
        paths under ARTIFACTS_DIR. Anything else (absolute paths elsewhere, unsafe keys) is never exposed.
        """
        if not path:
            return None
        if not Path(path).is_absolute():
            try:
                return validate_artifact_key(path.replace("\\", "/"))
            except InvalidArtifactKeyError:
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


IDEMPOTENT = frozenset({"navigate", "wait", "fill", "select"})
"""Safe to repeat. A click or key press is never repeated automatically: the first one may already have
worked (a second "Create Repository" could make a duplicate)."""

type Move = Literal["retry", "replan", "pause"]


class _Recovery:
    """The recovery budget of one run (agreed in #43): retry an idempotent step once, at most one replan per
    step and `max_replans` per run, and a pause for the human after 2 failed steps in a row."""

    def __init__(self, *, max_replans: int) -> None:
        self.max_replans = max_replans
        self.replans = 0
        self.retry_count = 0
        """Step retries plus replans (runs.retry_count, shown in the UI)."""
        self._retried: set[int] = set()
        self._replanned: set[int] = set()
        self._failed_in_a_row = 0

    def succeeded(self) -> None:
        self._failed_in_a_row = 0

    def after_failure(self, step: PlannedStep, out: StepOutcome) -> tuple[Move, str]:
        code = out.result.error.code if out.result.error else None
        if step.risk == "high":
            return "pause", "a high-risk step is never retried or replanned automatically"
        if code == "ambiguous_target":
            return "pause", "several elements match the target and none could be picked"
        if step.action.type in IDEMPOTENT and id(step) not in self._retried:
            self._retried.add(id(step))
            self.retry_count += 1
            return "retry", "retrying once"
        self._failed_in_a_row += 1
        if self._failed_in_a_row >= 2:
            return "pause", "two steps failed in a row"
        if id(step) in self._replanned or self.replans >= self.max_replans:
            return "pause", "the replan budget is used up"
        self._replanned.add(id(step))
        return "replan", _failure_reason(out)


def _failure_reason(out: StepOutcome) -> str:
    if out.result.error is not None:
        return f"the action failed ({out.result.error.code})"
    return "the expected state wasn't reached"


def _target_text(step: PlannedStep) -> str:
    target = step.target
    return " ".join(p for p in (target.role, target.name or target.selector) if p) or "the page"


def _failure_text(step: PlannedStep, out: StepOutcome) -> str:
    """For the replan prompt. Contains page text, so the planner puts it in an untrusted block."""
    expected = mask_expected(step.expected_state).model_dump(mode="json", exclude_none=True)
    lines = [
        f"Step: {step.instruction_text}",
        f"Action: {step.action.type} on {_target_text(step)}",
        f"Problem: {_failure_reason(out)}",
        f"Expected: {expected}",
        f"Observed: URL path {out.observed.url}, title {out.observed.title!r}",
    ]
    if out.verification is not None:
        lines += [f"- {c.kind} {c.expected}: {c.detail}" for c in out.verification.failures()]
    return "\n".join(lines)

"""In-process run executor (Phases 0-2): runs approved plans as asyncio tasks in the API process.

Phase 3 swaps this for an arq worker behind the same `RunExecutor` interface (docs/architecture.md §4).
Every status change and event goes through RunStore, one transaction each, so the database always holds
the truth. A crash leaves the run at its last committed status, and `recover()` fails it on the next start.
"""

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urljoin, urlsplit
from uuid import UUID

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from app.agent import (
    ActionExecutor,
    PlaywrightSession,
    SessionConfig,
    open_start_page,
    page_snapshot,
    start_path,
)
from app.agent.healer import HealBudget, HealChooser, HealOutcome, heal, stored_element
from app.agent.runlog import MASK, ScriptedStep, looks_sensitive, mask_expected, run_script
from app.agent.vision import VisionLocator, masked_screenshot
from app.contracts_gen.events_schema import PauseReason
from app.contracts_gen.plan_schema import PlannedStep
from app.db import WorkflowStepRow
from app.db.base import literal_values
from app.llm import LLMError, LLMRateLimitedError
from app.planner.instructions import tutorial_text
from app.planner.planner import Planner, PlannerError, PlanRequest
from app.planner.stepwise import StepContext, StepDecider
from app.ports.artifacts import ArtifactStore
from app.ports.models import (
    InvalidArtifactKeyError,
    ObservedState,
    PageState,
    PolicyDecision,
    validate_artifact_key,
)
from app.ports.observer import Observer
from app.ports.policy import Policy
from app.runs.profiles import ProfileStore
from app.runs.reverify import failure_details
from app.runs.states import RunStatus
from app.runs.steps import StepOutcome, act_and_record, act_and_verify, step_ref
from app.runs.store import RunJob, RunNotFoundError, RunStore
from app.runs.takeover import (
    TAKEOVER_REASONS,
    FrameSink,
    Notice,
    TakeoverError,
    TakeoverSession,
    host_of,
)

__all__ = ["TakeoverError"]
from app.targets import TargetSetup
from app.verifier import StepVerifier
from app.verifier.task_check import TaskChecker
from app.verifier.verifier import url_shown

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
    artifacts: ArtifactStore | None = None
    """Where the screenshot taken right before each action goes (#388). None: no such screenshot."""
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
    task_check: TaskChecker | None = None
    """Asked once after the last step whether the steps did the whole task (#274). None: not checked."""
    heal_chooser: HealChooser | None = None
    """Self-healing (#112): chooses among the candidates when scoring can't decide. None: scoring only."""
    heal_budget: HealBudget | None = None
    """The daily budget for `heal_chooser` (D12). None: the chooser is never asked."""
    profiles: ProfileStore | None = None
    """Each user's own site sessions (ADR 0007): do-it runs act in them, sign-in runs fill them."""
    takeover_idle_s: float = 300.0
    """A takeover with no input for this long ends; the run stays paused (ADR 0008, T9)."""
    decider: StepDecider | None = None
    """Step mode (ADR 0011): picks each next action from the page. None: step-mode runs fail at once."""
    max_steps: int = 20
    """Step mode: steps tried before the run pauses (`step_budget`); allow gives it as many again."""
    max_step_llm_calls: int = 25
    """Step mode: decisions (LLM calls) before the run pauses (`step_budget`)."""
    max_no_progress: int = 3
    """Step mode: decisions in a row whose action changed nothing visible; then the run pauses
    (`no_progress`)."""


HUMAN_CAP = 0.7
"""Confidence of a step a human did in a takeover (T8): below the 0.8 threshold, like an accepted unclear
step."""


def _verification(out: StepOutcome, *, by_hand: bool) -> dict[str, Any]:
    assert out.verification is not None
    stored = out.verification.verification.model_dump(mode="json")
    if by_hand:
        stored["confidence"] = min(stored["confidence"], HUMAN_CAP)
    return stored


@dataclass(frozen=True)
class _Pausable:
    page: Page
    step_seq: int
    hosts: tuple[str, ...]


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
        self._heals: dict[UUID, list[HealOutcome]] = {}
        """Steps a reverify run healed (#112): their outcomes, in step order."""
        self._takeover_pages: dict[UUID, _Pausable] = {}
        """Paused runs whose owner may take over the page (ADR 0008)."""
        self._takeovers: dict[UUID, TakeoverSession] = {}
        """Active takeovers: one controller per run."""
        self._handbacks: dict[UUID, str] = {}
        """What the owner said they did when handing back (barrier / step / rest), until the run uses it."""

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
        await self.end_takeover(run_id, "closed")  # an answer ends any takeover first, while still paused
        if decision == "deny":
            if not await self._store.cancel(run_id, reason="confirmation_denied"):
                return False
            await self._stop_task(run_id)
            return True
        resumed = {"step_seq": step_seq, "decision": "allow"}
        if not await self._store.transition(run_id, RunStatus.RUNNING, resumed, from_=RunStatus.PAUSED):
            return False
        return self.resume(run_id)

    async def stop(self, run_id: UUID) -> None:
        """Stop a run's steps and close its browser. The caller has already recorded why in the database (the
        API process cancels a run the worker runs, #95)."""
        await self._stop_task(run_id)

    def takeover(self, run_id: UUID) -> TakeoverSession | None:
        """The run's active takeover, if any."""
        return self._takeovers.get(run_id)

    async def start_takeover(
        self,
        run_id: UUID,
        on_frame: FrameSink,
        *,
        on_blocked: Notice | None = None,
        on_end: Notice | None = None,
    ) -> TakeoverSession:
        """Give the owner control of the paused page (ADR 0008). Raises TakeoverError `not_available` (not
        paused here, or not at a pause a human can resolve on the page) or `active` (someone has control)."""
        pausable = self._takeover_pages.get(run_id)
        if pausable is None:
            raise TakeoverError("not_available", "This run isn't paused at a step you can take over")
        if run_id in self._takeovers:
            raise TakeoverError("active", "Someone already has control of this run")

        async def ended(reason: str) -> None:
            self._takeovers.pop(run_id, None)
            data: dict[str, Any] = {"step_seq": pausable.step_seq, "reason": reason}
            if reason == "handed_back" and run_id in self._handbacks:
                data["done"] = self._handbacks[run_id]
            await self._store.paused_event(run_id, "takeover.ended", data)
            if on_end is not None:
                await on_end(reason)

        session = TakeoverSession(
            pausable.page,
            allowed_hosts=pausable.hosts,
            on_end=ended,
            on_blocked=on_blocked,
            idle_s=self._env.takeover_idle_s,
            step_seq=pausable.step_seq,
        )
        self._takeovers[run_id] = session
        if not await self._store.paused_event(run_id, "takeover.started", {"step_seq": pausable.step_seq}):
            self._takeovers.pop(run_id, None)
            raise TakeoverError("not_available", "This run is no longer paused")
        await session.start(on_frame)
        return session

    async def hand_back(self, run_id: UUID, step_seq: int, done: str) -> bool:
        """End the owner's takeover and continue the run (ADR 0008, T7). `done`: barrier (act on the step
        again), step (verify it without acting) or rest (verify the end state). False without an active
        takeover at `step_seq`."""
        session = self._takeovers.get(run_id)
        pausable = self._takeover_pages.get(run_id)
        if session is None or pausable is None or pausable.step_seq != step_seq:
            return False
        self._handbacks[run_id] = done
        await session.end("handed_back")
        resumed = {"step_seq": step_seq, "decision": "allow"}
        if not await self._store.transition(run_id, RunStatus.RUNNING, resumed, from_=RunStatus.PAUSED):
            self._handbacks.pop(run_id, None)
            return False
        return self.resume(run_id)

    async def end_takeover(self, run_id: UUID, reason: str) -> None:
        session = self._takeovers.get(run_id)
        if session is not None:
            await session.end(reason)

    def resume(self, run_id: UUID) -> bool:
        """Let a paused run go on. The caller has already moved it back to running in the database. False if
        it isn't waiting here."""
        waiting = self._answers.get(run_id)
        if waiting is None or waiting.done():
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
            finally:
                self._heals.pop(run_id, None)  # a run that failed or stopped saves no heals

    async def _run(self, run_id: UUID) -> None:
        job = await self._store.load(run_id)
        if job.status is not RunStatus.QUEUED:
            return  # cancelled while waiting for a slot, or submitted twice
        # Step mode has no steps yet: the outline items stand for them (contracts 1.21).
        total = len(job.outline) if job.mode == "steps" else len(job.steps)
        started = {"plan_id": str(job.plan_id), "total_steps": max(total, 1)}
        if not await self._store.transition(
            run_id, RunStatus.RUNNING, started, from_=RunStatus.QUEUED, started_at=datetime.now(UTC)
        ):
            return
        t0 = time.perf_counter()
        env = self._env
        target = env.target(job)
        if job.kind == "sign_in":
            await self._sign_in(job, target)
            return
        profile = None
        if job.kind == "do_it" and target.login_path is not None and env.profiles is not None:
            # The user's own account (ADR 0007): their session, never the shared test account's.
            profile = await env.profiles.load(job.user_id, target.site or "") if job.user_id else None
            if profile is None:
                await self._fail_sign_in(
                    run_id, f"Sign in to {target.site} first: Krama acts in your own account."
                )
                return
            target = replace(
                target, storage_state=profile.state, sign_in_problem=None, signed_in_as=profile.account
            )
        job = replace(job, recorded_as=target.signed_in_as)
        if target.sign_in_problem is not None:
            await self._fail_sign_in(run_id, target.sign_in_problem)
            return
        config = target.browser_config(env.session_config(job))
        # A do-it run acts in a real account (P10, P16): no vision guesses, no heals, no LLM but the policy's.
        do_it = job.kind == "do_it"
        async with PlaywrightSession(config) as session:
            page = session.page
            executor = ActionExecutor(page, vision=None if do_it else env.vision, settle_ms=target.settle_ms)
            if not await open_start_page(page, start_path(job.target_url)):
                await self._store.fail(
                    run_id, from_=RunStatus.RUNNING, message=f"Couldn't open {job.target_url}",
                    reason="site_unreachable",
                )  # fmt: skip
                return
            if target.signed_in_check is not None and not await target.signed_in_check(page):
                await self._fail_sign_in(run_id, "The stored session no longer signs in. Log in again.")
                return
            if (
                profile is not None
                and env.profiles is not None
                and target.account_of is not None
                and job.user_id is not None
            ):
                # The site may have dropped the session (a restart, a sign-out elsewhere): ask it who is
                # signed in before acting, instead of failing a step on a signed-out page. A dead session
                # is forgotten, so "Do it for me" asks the user to sign in again.
                state = dict(await page.context.storage_state())
                if await target.account_of(page, state) is None:
                    await env.profiles.delete(job.user_id, target.site or "")
                    await self._fail_sign_in(
                        run_id, f"Your sign-in to {target.site} has expired. Sign in again, then run it."
                    )
                    return
            setup = [] if profile is not None else list(env.preconditions(job))
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
            recording = None
            if not do_it:  # a do-it run shows the user's own data: no rrweb recording is kept (P14)
                await observer.start_recording(page)
            try:
                verify_timeout_s = target.verify_timeout_s or env.verify_timeout_s
                if job.mode == "steps" and job.kind == "task":
                    rows = await self._decided(job, executor, observer, page, verify_timeout_s)
                else:
                    rows = await self._steps(job, executor, observer, page, verify_timeout_s)
            finally:
                if not do_it:
                    recording = await observer.stop_recording()
            missing = await self._missing_part(job, rows, page) if rows is not None else None
        if rows is None:
            return  # failed, paused out or cancelled; the store already says so
        if missing is not None:
            await self._store.fail(
                run_id, from_=RunStatus.RUNNING, message=f"The steps didn't do the whole task: {missing}",
                reason="task_incomplete", missing=missing,
            )  # fmt: skip
            return
        if recording is None:  # do_it: the run is the record; nothing is stored on the workflow (P9)
            duration_ms = round((time.perf_counter() - t0) * 1000)
            await self._store.complete_reverify(job, verified_steps=len(rows), duration_ms=duration_ms)
            return
        self._to_recording_offsets(rows, recording.path)
        if job.kind == "reverify":
            duration_ms = round((time.perf_counter() - t0) * 1000)
            heals = self._heals.pop(run_id, [])
            if not heals:
                await self._store.complete_reverify(job, verified_steps=len(rows), duration_ms=duration_ms)
                return
            # Every step verified after a heal: what ran is the workflow's next version (D8: a Gemini heal
            # waits for a human, a deterministic one is published).
            await self._store.complete_heal(
                job,
                rows,
                needs_review=any(h.how == "gemini" for h in heals),
                confidence=min((r.verification["confidence"] for r in rows), default=1.0),
                recording_path=self._artifact_key(recording.path),
                viewport=_viewport(config),
                duration_ms=duration_ms,
            )
            return
        await self._store.complete(
            job,
            rows,
            confidence=min((r.verification["confidence"] for r in rows), default=1.0),
            recording_path=self._artifact_key(recording.path),
            viewport=_viewport(config),
            duration_ms=round((time.perf_counter() - t0) * 1000),
        )

    async def _steps(
        self, job: RunJob, executor: ActionExecutor, observer: Observer, page: Page, verify_timeout_s: float
    ) -> list[WorkflowStepRow] | None:
        """Every step in order, with recovery (docs/research/phase-1-vishwas-agent-recovery.md): retry an
        idempotent step once, else replan the rest (a human re-approves it), else pause for the human.
        The rows of the finished steps, or None if the run stopped."""
        env, store = self._env, self._store
        steps = list(job.steps)
        rows: list[WorkflowStepRow] = []
        budget = _Recovery(max_replans=env.max_replans_per_run)
        self._paused_s[job.run_id] = 0.0
        stored: dict[int, dict[str, Any]] = {}
        if job.kind == "reverify" and job.source_workflow_id is not None:
            stored = await store.stored_targets(job.source_workflow_id)
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
            out = await self._attempt(
                job, step, executor, observer, page, budget.retry_count, verify_timeout_s
            )
            if out is None:
                return None  # stopped by the policy, or cancelled
            if out.by_hand_pending:
                by_hand = await self._by_hand(job, steps, i, rows, observer, page, verify_timeout_s)
                if by_hand == "stopped":
                    return None
                if by_hand == "rest":
                    return rows
                if by_hand == "step":
                    budget.succeeded()
                    i += 1
                continue  # retry / none: act on the step now
            if out.verified:
                rows.append(self._row(job, step, out))
                budget.succeeded()
                i += 1
                continue
            if out.unclear:
                message = (
                    "Nothing proved this step worked. Check the page: allow accepts the step, deny cancels."
                )
                if not await self._pause(job, step.seq, "verification_unclear", message, page=page):
                    return None
                by_hand = await self._by_hand(job, steps, i, rows, observer, page, verify_timeout_s)
                if by_hand == "stopped":
                    return None
                if by_hand == "retry":
                    continue  # the owner cleared what was in the way: act on the step again
                if by_hand == "rest":
                    return rows
                if by_hand == "none":
                    rows.append(self._row(job, step, out))  # a human accepted it; confidence stays below 0.8
                budget.succeeded()
                i += 1
                continue

            move, why = budget.after_failure(step, out)
            if move == "retry":
                continue  # same step again; budget.retry_count already counts it
            if job.kind == "do_it":
                # The user's real change: no replan, no "try once more", never the whole run again (P7).
                await self._fail_reverify(job, step, out)
                return None
            if job.kind == "reverify":
                healed = await self._heal(job, step, out, stored.get(step.seq), executor, observer, page,
                                          budget.retry_count, verify_timeout_s)  # fmt: skip
                if healed.stopped:
                    return None  # the policy stopped the healed step, or the run was cancelled
                if healed.step is not None and healed.out is not None:
                    steps[i] = healed.step
                    rows.append(self._row(job, healed.step, healed.out))
                    budget.succeeded()
                    i += 1
                    continue  # the later steps must verify too, or the run fails and nothing is saved
                await self._fail_reverify(job, step, out, healed.outcome)
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
                page=page,
            ):
                return None
            by_hand = await self._by_hand(job, steps, i, rows, observer, page, verify_timeout_s)
            if by_hand == "stopped":
                return None
            if by_hand == "rest":
                return rows
            if by_hand == "step":
                budget.succeeded()
                i += 1
                continue
            budget.retry_count += 1  # the human asked for one more try (or cleared the way first)
        return rows

    async def _decided(
        self, job: RunJob, executor: ActionExecutor, observer: Observer, page: Page, verify_timeout_s: float
    ) -> list[WorkflowStepRow] | None:
        """Step mode (ADR 0011, #470): look at the page, decide one action, act, keep what visibly changed as
        that step's expected state; until the agent says the task is done. Every action goes through the
        policy, and risky ones pause, as in a planned run. The rows of the steps that verified (numbered from
        1), or None if the run stopped."""
        env, store = self._env, self._store
        if env.decider is None:
            await store.fail(
                job.run_id, from_=RunStatus.RUNNING, message="This server can't run step-mode plans",
                reason="no_decider",
            )  # fmt: skip
            return None
        rows: list[WorkflowStepRow] = []
        done: list[str] = []
        calls = stalled = 0
        max_steps, max_calls = env.max_steps, env.max_step_llm_calls
        suffix = f"{secrets.randbelow(9000) + 1000}"
        self._paused_s[job.run_id] = 0.0
        t0 = time.perf_counter()
        seq = 1
        while True:
            if time.perf_counter() - t0 - self._paused_s[job.run_id] > env.run_timeout_s:
                await store.fail(
                    job.run_id, from_=RunStatus.RUNNING, reason="run_timeout", step_seq=seq,
                    message=f"The run took longer than {env.run_timeout_s:g} s (pauses not counted)",
                )  # fmt: skip
                return None
            if seq > max_steps or calls >= max_calls:
                message = (
                    f"Krama took {seq - 1} steps and {calls} decisions without finishing. Allow gives it as "
                    "many again; deny cancels."
                )
                if not await self._pause(job, seq, "step_budget", message, page=page):
                    return None
                max_steps, max_calls = seq - 1 + env.max_steps, calls + env.max_step_llm_calls
            ctx = StepContext(
                task=job.prompt,
                outline=job.outline,
                done=done,
                path=self._mask(urlsplit(page.url).path or "/"),
                page_snapshot=await self._masked_snapshot(page),
                example_suffix=suffix,
            )
            try:
                decision = await env.decider.decide(ctx, seq=seq)
            except LLMRateLimitedError:
                await store.fail(
                    job.run_id, from_=RunStatus.RUNNING, message="The LLM is out of quota",
                    code="rate_limited", reason="llm_quota", step_seq=seq,
                )  # fmt: skip
                return None
            except LLMError as e:
                await store.fail(
                    job.run_id, from_=RunStatus.RUNNING, code="llm_unavailable", reason="llm_unavailable",
                    message=f"The LLM couldn't decide the next step ({e})", step_seq=seq,
                )  # fmt: skip
                return None
            calls += 1
            if decision.step is None:
                if not rows:
                    await store.fail(
                        job.run_id, from_=RunStatus.RUNNING, reason="nothing_to_do", step_seq=seq,
                        message="Krama found nothing to do: the page already looks like the task is done",
                    )  # fmt: skip
                    return None
                return rows
            step = decision.step
            decided = {
                "step_seq": seq,
                "outline_seq": decision.outline_seq,
                "thought": self._mask(decision.thought),
                "action": step.action.model_dump(mode="json", exclude_none=True),
                "target": step.target.model_dump(mode="json", exclude_none=True) or None,
            }
            if not await store.event(job.run_id, "step.decided", decided):
                return None
            attempt = await self._attempt_decided(job, step, executor, observer, page, verify_timeout_s)
            if attempt is None:
                return None  # stopped by the policy, or cancelled
            recorded, out = attempt
            if out.by_hand_pending:
                done.append("(The user did something by hand here; look at the page again.)")
                stalled = 0
            elif out.verified:
                rows.append(self._row(job, recorded.model_copy(update={"seq": len(rows) + 1}), out))
                done.append(rows[-1].instruction_text)
                stalled = 0
            else:
                stalled += 1
                error = out.result.error
                why = f"it failed ({error.code})" if error is not None else "nothing visible changed"
                done.append(f"(Tried, not done: {step.instruction_text} {why}.)")
                if stalled >= env.max_no_progress:
                    message = (
                        f"The last {stalled} actions changed nothing on the page. Take over to help, then "
                        "allow to let Krama look again; deny cancels."
                    )
                    if not await self._pause(job, seq, "no_progress", message, page=page):
                        return None
                    self._handbacks.pop(job.run_id, None)
                    stalled = 0
            seq += 1

    async def _attempt_decided(
        self,
        job: RunJob,
        step: PlannedStep,
        executor: ActionExecutor,
        observer: Observer,
        page: Page,
        verify_timeout_s: float,
    ) -> tuple[PlannedStep, StepOutcome] | None:
        """One decided step, announced on the live view like a planned one. The step comes back with the
        expected state it reached. None if the run stopped (policy, cancel)."""
        store, seq = self._store, step.seq
        if not await store.event(
            job.run_id, "step.started", {"step_seq": seq, "instruction_text": step.instruction_text},
            current_seq=seq, retry_count=0,
        ):  # fmt: skip
            return None
        before = await observer.capture(page, step_ref(step))
        if not await self._allowed(job, step, before, page):
            return None
        if self._handbacks.pop(job.run_id, None) is not None:  # the owner took over at the policy's pause
            return step, StepOutcome.pending_by_hand(before)
        recorded, out = await act_and_record(
            step,
            executor,
            observer,
            self._env.verifier,
            page,
            before=before,
            change_timeout_s=verify_timeout_s,
            check_interval_s=self._env.verify_interval_s,
            focus_shot=lambda: self._focus_shot(job, seq, page),
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
            return (recorded, out) if await store.event(job.run_id, "step.verified", verified) else None
        failed = {
            "step_seq": seq,
            "expected": {},
            "observed": {"url": url_shown(out.observed.url, out.observed.query), "title": out.observed.title},
            "screenshot_url": shot,
        }
        return (recorded, out) if await store.event(job.run_id, "step.failed", failed) else None

    async def _attempt(
        self,
        job: RunJob,
        step: PlannedStep,
        executor: ActionExecutor,
        observer: Observer,
        page: Page,
        retry_count: int,
        verify_timeout_s: float,
    ) -> StepOutcome | None:
        """One try of one step, announced on the live view. None if the run stopped (policy, cancel)."""
        store, seq = self._store, step.seq
        if not await store.event(
            job.run_id, "step.started", {"step_seq": seq, "instruction_text": step.instruction_text},
            current_seq=seq, retry_count=retry_count,
        ):  # fmt: skip
            return None  # cancelled meanwhile
        before = await observer.capture(page, step_ref(step))
        if not await self._allowed(job, step, before, page):
            return None
        if job.run_id in self._handbacks:  # the owner took over at the policy's pause (login wall, challenge)
            return StepOutcome.pending_by_hand(before)
        out = await act_and_verify(
            step,
            executor,
            observer,
            self._env.verifier,
            page,
            verify_timeout_s=verify_timeout_s,
            verify_interval_s=self._env.verify_interval_s,
            before=before,
            focus_shot=lambda: self._focus_shot(job, seq, page),
            vision=job.kind != "do_it",
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
            "observed": {"url": url_shown(out.observed.url, out.observed.query), "title": out.observed.title},
            "screenshot_url": shot,
        }
        return out if await store.event(job.run_id, "step.failed", failed) else None

    async def _by_hand(
        self,
        job: RunJob,
        steps: list[PlannedStep],
        i: int,
        rows: list[WorkflowStepRow],
        observer: Observer,
        page: Page,
        verify_timeout_s: float,
    ) -> str:
        """After a pause: what the owner's hand-back means (ADR 0008, T7). `none`: no takeover happened;
        `retry`: they cleared a barrier, act on the step again; `step`: steps[i] was done by hand and is in
        `rows`; `rest`: every remaining step was done by hand and is in `rows`; `stopped`: the run ended.

        What they did is checked on the page as it is, without acting. If that fails, the run pauses again;
        allowing it then accepts their word for it (below the 0.8 threshold, like an accepted unclear
        step)."""
        done = self._handbacks.pop(job.run_id, None)
        if done is None:
            return "none"
        if done == "barrier":
            return "retry"
        todo = steps[i : i + 1] if done == "step" else steps[i:]
        while True:
            out = await act_and_verify(
                todo[-1], ActionExecutor(page), observer, self._env.verifier, page,
                verify_timeout_s=verify_timeout_s, verify_interval_s=self._env.verify_interval_s,
                vision=job.kind != "do_it", act=False,
            )  # fmt: skip
            if out.verified:
                break
            message = "Krama couldn't confirm what was done by hand. Take over again, or allow to accept it."
            if not await self._pause(job, steps[i].seq, "verification_unclear", message, page=page):
                return "stopped"
            again = self._handbacks.pop(job.run_id, None)
            if again is None:
                break  # the owner allowed it: their word stands
            if again == "barrier":
                return "retry"
            todo = steps[i : i + 1] if again == "step" else steps[i:]
            done = again
        for step in todo:
            rows.append(self._row(job, step, out, by_hand=True))
            assert out.verification is not None
            v = out.verification.verification
            data = {
                "step_seq": step.seq,
                "method": list(v.method),
                "confidence": min(v.confidence, HUMAN_CAP),
                "performed_by": "human",
            }
            if not await self._store.event(job.run_id, "step.verified", data):
                return "stopped"
        return "step" if done == "step" else "rest"

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
            practice_repo=setup.practice_repo,
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

    async def _missing_part(self, job: RunJob, rows: Sequence[WorkflowStepRow], page: Page) -> str | None:
        """What part of the task the verified steps left out, or None (done, unsure, or not checked). A
        reverify replays a stored workflow, so only task runs are checked."""
        if self._env.task_check is None or job.kind != "task":
            return None
        verdict = await self._env.task_check.check(
            job.prompt,
            [r.instruction_text for r in rows],
            self._mask(urlsplit(page.url).path or "/"),
            await self._masked_snapshot(page),
        )
        logger.info("task check for run %s: done=%s (%d LLM attempts)", job.run_id, verdict.done,
                    len(verdict.attempts))  # fmt: skip
        if verdict.done is not False:
            return None
        return verdict.missing or "part of the task"

    async def _sign_in(self, job: RunJob, target: TargetSetup) -> None:
        """A sign-in run (ADR 0007): the site's sign-in page in a fresh browser, paused for the owner to sign
        in by hand in a takeover. Each hand-back, Krama asks the site who is signed in; once someone is, it
        stores the session for this user and site and completes. No recording: passwords are typed here."""
        env, store = self._env, self._store
        if target.login_path is None or target.account_of is None or target.site is None:
            await store.fail(
                job.run_id,
                from_=RunStatus.RUNNING,
                message="This site has no sign-in Krama can keep",
                reason="sign_in_unsupported",
            )
            return
        if env.profiles is None or job.user_id is None:
            await store.fail(
                job.run_id,
                from_=RunStatus.RUNNING,
                message="Sessions can't be stored here",
                reason="sign_in_unsupported",
            )
            return
        config = replace(target, storage_state=None).browser_config(env.session_config(job))
        async with PlaywrightSession(config) as session:
            page = session.page
            try:
                await page.goto(urljoin(job.target_url, target.login_path))
            except PlaywrightError:
                await store.fail(
                    job.run_id,
                    from_=RunStatus.RUNNING,
                    message=f"Couldn't open {job.target_url}",
                    reason="site_unreachable",
                )
                return
            message = f"Sign in to {target.site} yourself: take over the page, sign in, then hand it back."
            # Step 1 starts like any step: without it the run paused with no current step, and "allow" or
            # "deny" on the pause answered 409 (#431 gate).
            if not await store.event(
                job.run_id, "step.started", {"step_seq": 1, "instruction_text": f"Sign in to {target.site}"},
                current_seq=1, retry_count=0,
            ):  # fmt: skip
                return
            for _ in range(5):
                if not await self._pause(job, 1, "auth_wall", message, page=page):
                    return
                self._handbacks.pop(job.run_id, None)
                state = await page.context.storage_state()
                account = await target.account_of(page, dict(state))
                if account:
                    await env.profiles.save(
                        job.user_id, target.site, account, dict(state), session_cookie=target.session_cookie
                    )
                    # The step is done (by the owner) and checked (the site names the account): without
                    # this the finished run showed its one step as "Pending" (#451).
                    verified = {"step_seq": 1, "method": ["dom"], "confidence": 0.7, "performed_by": "human"}
                    if not await store.event(job.run_id, "step.verified", verified):
                        return
                    await store.complete_sign_in(job, verified_steps=1)
                    return
                message = "Krama can't see that you're signed in yet. Take over again and finish signing in."
        await store.fail(
            job.run_id, from_=RunStatus.RUNNING, message="Not signed in after 5 tries", reason="not_signed_in"
        )

    async def _fail_sign_in(self, run_id: UUID, message: str) -> None:
        """The target needs a signed-in session we don't have (#87): stop before step 1, say how to fix it."""
        await self._store.fail(run_id, from_=RunStatus.RUNNING, message=message, reason="sign_in_required")

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

    async def _allowed(self, job: RunJob, step: PlannedStep, before: ObservedState, page: Page) -> bool:
        """Ask the policy before acting (AGENTS.md §4). True to go ahead; False if the run stopped."""
        decision = PolicyDecision(verdict="allow")
        if self._env.policy is not None:
            state = PageState(url=before.url, title=before.title, aria_excerpt=before.aria_excerpt)
            decision = await self._env.policy.check_action(step_ref(step), state)
        if decision.verdict == "allow" and step.risk == "high":
            # The approved plan itself says this step is risky: a human confirms it right before it runs.
            message = "The plan marks this step as high risk."
            decision = PolicyDecision(verdict="pause", reason="destructive_action", message=message)
        if decision.verdict == "allow":
            return True
        if decision.verdict == "pause" and decision.reason in PAUSE_REASONS:
            return await self._pause(job, step.seq, decision.reason, decision.message or None, page=page)
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

    async def _heal(
        self,
        job: RunJob,
        step: PlannedStep,
        out: StepOutcome,
        stored: dict[str, Any] | None,
        executor: ActionExecutor,
        observer: Observer,
        page: Page,
        retry_count: int,
        verify_timeout_s: float,
    ) -> "_HealAttempt":
        """Self-healing (#112, phase-4-vishwas-self-healing-locators.md) after a reverify step's element went
        missing: pick the element that is the target now, then run the step again on it through the normal
        path, so the policy checks the new target and the verifier decides."""
        error = out.result.error
        if error is None or error.code != "target_not_found" or not step.target.role or step.risk == "high":
            return _HealAttempt(None)  # ambiguous: role+name can't single out a look-alike; high risk: never
        outcome = await heal(
            page,
            stored_element(stored or step.target.model_dump(exclude_none=True)),
            list(out.result.candidates),
            instruction=step.instruction_text,
            expected=step.expected_state,
            chooser=self._env.heal_chooser,
            budget=self._env.heal_budget,
        )
        logger.info("heal for run %s step %s: %s", job.run_id, step.seq, outcome.reason)
        if outcome.target is None:
            return _HealAttempt(outcome)
        healed = step.model_copy(update={"target": outcome.target})
        again = await self._attempt(job, healed, executor, observer, page, retry_count, verify_timeout_s)
        if again is None:
            return _HealAttempt(outcome, stopped=True)
        if not again.verified:
            failed = replace(
                outcome, target=None, reason=f"{outcome.reason}, but the step didn't verify on it"
            )
            return _HealAttempt(failed)
        self._heals.setdefault(job.run_id, []).append(outcome)
        return _HealAttempt(outcome, healed, again)

    async def _fail_reverify(
        self, job: RunJob, step: PlannedStep, out: StepOutcome, heal: "HealOutcome | None" = None
    ) -> None:
        """A stored step no longer works. locator_miss: its element is gone or ambiguous (the UI changed);
        action_failed: the action itself failed; state_mismatch: it ran but its expected state didn't hold."""
        error = out.result.error
        if error is not None and error.code in ("target_not_found", "ambiguous_target"):
            reason, what = "locator_miss", f"its element wasn't found ({error.code})"
        elif error is not None:
            reason, what = "action_failed", f"its action failed ({error.code})"
        else:
            reason, what = "state_mismatch", "it ran, but the expected state didn't hold"
        lead = "failed" if job.kind == "do_it" else "no longer works"
        await self._store.fail(
            job.run_id, from_=RunStatus.RUNNING, message=f"Step {step.seq} {lead}: {what}",
            reason=reason, step_seq=step.seq, **failure_details(step, out, heal),
        )  # fmt: skip

    async def _pause(
        self,
        job: RunJob,
        step_seq: int,
        reason: str,
        message: str | None = None,
        *,
        plan_id: UUID | None = None,
        page: Page | None = None,
    ) -> bool:
        """Pause with the browser open until /confirm. True if a human allowed it (deny cancels the task).

        A reverify run has nobody watching it: instead of pausing it fails, with the pause reason. With
        `page`, a pause a human can resolve on the page itself lets the owner take it over (ADR 0008)."""
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
            if page is not None and reason in TAKEOVER_REASONS:
                hosts = (host_of(job.target_url), *self._env.target(job).sign_in_hosts)
                self._takeover_pages[job.run_id] = _Pausable(page, step_seq, hosts)
                paused["takeover_available"] = True
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
            self._takeover_pages.pop(job.run_id, None)
            # Still active only if the pause ended without an answer (cancel, timeout): its WebSocket closes.
            await self.end_takeover(job.run_id, "cancelled")
            if job.run_id in self._paused_s:
                self._paused_s[job.run_id] += time.perf_counter() - t0

    def _row(
        self, job: RunJob, step: PlannedStep, out: StepOutcome, *, by_hand: bool = False
    ) -> WorkflowStepRow:
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
                # What a healer compares a changed page against (#112, D2). Internal: not in the contract.
                "fingerprint": out.result.element.model_dump(mode="json", exclude_none=True)
                if out.result.element
                else None,
            },
            instruction_text=self._step_text(job, step, out, sensitive=sensitive),
            expected_state=mask_expected(step.expected_state).model_dump(mode="json", exclude_none=True),
            before_state=_before_state(out),
            observed_state={
                "url": out.observed.url,
                "query": out.observed.query,
                "title": out.observed.title,
                "headings": out.observed.headings,
                "screenshot_path": key,
                "captured_at": out.observed.captured_at.isoformat(),
            },
            verification=_verification(out, by_hand=by_hand),
            risk=step.risk,
            performed_by="human" if by_hand else "krama",
            sensitive=sensitive,
            screenshot_path=key,
            # Wall-clock epoch ms for now; _to_recording_offsets turns them into offsets into the recording.
            start_ms=_epoch_ms(out.result.started_at),
            end_ms=_epoch_ms(out.observed.captured_at),
        )

    def _to_recording_offsets(self, rows: list[WorkflowStepRow], recording_path: str | None) -> None:
        """Each step's start/end as ms since the recording's first event: the timeline the player replays
        (contract: workflow_steps.start_ms/end_ms). rrweb timestamps are the browser's Date.now(), the same
        clock as ours. Without a readable recording the steps get no timing rather than a wrong one."""
        base = self._first_event_ms(recording_path)
        for row in rows:
            if base is None or row.start_ms is None or row.end_ms is None:
                row.start_ms = row.end_ms = None
                continue
            row.start_ms = max(0, row.start_ms - base)
            row.end_ms = max(row.start_ms, row.end_ms - base)

    def _first_event_ms(self, recording_path: str | None) -> int | None:
        key = self._artifact_key(recording_path)
        if key is None:
            return None
        try:
            events = json.loads((self._env.artifacts_dir / key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if isinstance(events, dict):
            events = events.get("events", [])
        stamps: list[int] = [
            e["timestamp"] for e in events if isinstance(e, dict) and isinstance(e.get("timestamp"), int)
        ]
        return min(stamps) if stamps else None

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

    async def _focus_shot(self, job: RunJob, seq: int, page: Page) -> str | None:
        """The page right before the action, target scrolled into view, sensitive fields masked (#388). The
        video shows it for a click: the observer's screenshot is taken after the action, often on the next
        page. A failure here only costs the video its better frame, never the step."""
        if self._env.artifacts is None:
            return None
        try:
            ref = await self._env.artifacts.put(
                f"runs/{job.run_id}/steps/{seq}_focus.png", await masked_screenshot(page), "image/png"
            )
        except Exception:
            logger.warning("Step %d: no screenshot before the action", seq, exc_info=True)
            return None
        return ref.key

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


def _before_state(out: StepOutcome) -> dict[str, Any] | None:
    """The page before the action. Its screenshot is the one taken with the target in view (#388)."""
    if out.before is None:
        return None
    state = _summary(out.before)
    if out.focus_screenshot:
        state["screenshot_path"] = out.focus_screenshot
    return state


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


def _epoch_ms(moment: datetime | None) -> int | None:
    return round(moment.timestamp() * 1000) if moment is not None else None


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
        f"Observed: URL {url_shown(out.observed.url, out.observed.query)}, title {out.observed.title!r}",
    ]
    if out.verification is not None:
        lines += [f"- {c.kind} {c.expected}: {c.detail}" for c in out.verification.failures()]
    return "\n".join(lines)


@dataclass(frozen=True)
class _HealAttempt:
    outcome: HealOutcome | None
    """Why it healed or not; None when healing doesn't apply to the failure."""
    step: PlannedStep | None = None
    """The step with its new target, when it verified on it."""
    out: StepOutcome | None = None
    stopped: bool = False
    """The run stopped on the healed step (policy stop, cancel): the store already says so."""


def _viewport(config: SessionConfig) -> dict[str, Any]:
    return {
        "width": config.viewport_width,
        "height": config.viewport_height,
        "device_scale_factor": config.device_scale_factor,
    }

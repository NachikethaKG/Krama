"""`krama run`: plan → approve → execute → observe → verify, one task, one browser."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Page

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig
from app.agent.runlog import MASK, ScriptedStep, looks_sensitive, run_script
from app.contracts_gen.plan_schema import Plan, PlannedStep
from app.llm import LLMError
from app.planner import InvalidPlanError, NeedsClarificationError, Planner, PlanRequest
from app.ports.models import ObservedState, StepRef
from app.ports.observer import Observer
from app.runs.report import ObservedSummary, RunReport, RunStatus, StepReport
from app.verifier import VerificationOutcome, Verifier

type Approve = Callable[[Plan], Awaitable[bool]]
type Notify = Callable[[str], None]


@dataclass
class RunOptions:
    task: str
    target_url: str
    site: str | None = None
    start_path: str = "/"
    """Opened first, before the preconditions (e.g. the login page or dashboard)."""
    preconditions: Sequence[ScriptedStep] = ()
    """Setup before planning, e.g. logging in. Not part of the plan or the recording."""
    signed_in_as: str | None = None
    headless: bool = True
    verify_timeout_s: float = 5.0
    """How long a step may take to reach its expected state (pages can still be loading after a click)."""
    verify_interval_s: float = 0.25
    session: SessionConfig | None = None
    on_event: Notify = field(default=lambda _: None)


@dataclass
class RunParts:
    planner: Planner
    verifier: Verifier
    observer_for: Callable[[Path], Observer]
    """Builds the observer for one run, given the run's artifact folder (screenshots, rrweb recording)."""
    approve: Approve


async def run_task(options: RunOptions, parts: RunParts, *, artifacts_dir: Path) -> RunReport:
    report = RunReport(task=options.task, target_url=options.target_url, started_at=datetime.now(UTC))
    t0 = time.perf_counter()
    say = options.on_event
    config = options.session or SessionConfig(base_url=options.target_url, headless=options.headless)
    try:
        async with PlaywrightSession(config) as session:
            page = session.page
            executor = ActionExecutor(page)
            observer = parts.observer_for(report.run_dir(artifacts_dir))
            await page.goto(options.start_path, wait_until="domcontentloaded")

            if options.preconditions:
                setup = await run_script(
                    executor, list(options.preconditions), task="preconditions", base_url=options.target_url
                )
                report.preconditions = setup.entries
                if not setup.ok:
                    failed = setup.failed_entry
                    return _finish(
                        report, t0, "error", f"precondition failed: {failed.result.error if failed else ''}"
                    )

            say("Planning…")
            try:
                result = await parts.planner.plan(
                    PlanRequest(
                        task_id=report.run_id,
                        task=options.task,
                        start_path=executor.current_path(),
                        page_snapshot=await _page_snapshot(page),
                        site=options.site,
                        signed_in_as=options.signed_in_as,
                    )
                )
            except NeedsClarificationError as e:
                report.llm_attempts = e.llm_attempts
                return _finish(report, t0, "needs_clarification", e.question)
            except (InvalidPlanError, LLMError) as e:
                report.llm_attempts = getattr(e, "llm_attempts", None) or getattr(e, "attempts", [])
                return _finish(report, t0, "error", f"planning failed: {e}")
            report.plan = _masked(result.plan)  # the log never holds typed passwords
            report.planner_model, report.llm_attempts = result.model, result.llm_attempts

            if not await parts.approve(result.plan):
                return _finish(report, t0, "rejected", "plan rejected")

            await observer.start_recording(page)
            try:
                for step in result.plan.steps:
                    step_report = await _run_step(step, executor, observer, parts.verifier, options, page)
                    report.steps.append(step_report)
                    say(_line(step_report))
                    if not (step_report.verification and step_report.verification.verified):
                        return _finish(report, t0, "failed", f"step {step.seq} did not verify")
            finally:
                report.recording = await observer.stop_recording()
            return _finish(report, t0, "verified", "every step verified")
    except Exception as e:  # a crash still leaves a run log behind
        return _finish(report, t0, "error", f"{type(e).__name__}: {e}")


async def _run_step(
    step: PlannedStep,
    executor: ActionExecutor,
    observer: Observer,
    verifier: Verifier,
    options: RunOptions,
    page: Page,
) -> StepReport:
    # ports/models.py still has provisional copies of Action/Target, so cross the port as plain data.
    ref = StepRef.model_validate(step.model_dump(include={"seq", "action", "target", "instruction_text"}))
    result = await executor.execute(step.action, step.target)
    logged_action = step.action
    if step.action.value is not None and looks_sensitive(step.target.name):
        logged_action = step.action.model_copy(update={"value": MASK})

    observed: ObservedState = await observer.capture(page, ref)
    outcome: VerificationOutcome | None = None
    attempts = 0
    if result.ok:
        deadline = time.perf_counter() + options.verify_timeout_s
        while True:
            attempts += 1
            outcome = verifier.verify(step.expected_state, observed)
            if outcome.verified or time.perf_counter() >= deadline:
                break
            await asyncio.sleep(options.verify_interval_s)
            observed = await observer.capture(page, ref)

    return StepReport(
        seq=step.seq,
        instruction_text=step.instruction_text,
        action=logged_action,
        target=step.target,
        risk=step.risk,
        result=result,
        observed=ObservedSummary(
            url=observed.url, title=observed.title, screenshot_path=observed.screenshot_path
        ),
        verification=outcome,
        verify_attempts=attempts,
    )


def _masked(plan: Plan) -> Plan:
    steps = [
        s.model_copy(update={"action": s.action.model_copy(update={"value": MASK})})
        if s.action.value is not None and looks_sensitive(s.target.name)
        else s
        for s in plan.steps
    ]
    return plan.model_copy(update={"steps": steps})


async def _page_snapshot(page: Page) -> str:
    """ARIA snapshot of the start page for the planner, which redacts it again before the LLM sees it."""
    for locator in (page.get_by_role("main").first, page.locator("body")):
        try:
            return await locator.aria_snapshot(timeout=2_000)
        except Exception:
            continue
    return ""


def _finish(report: RunReport, t0: float, status: RunStatus, message: str) -> RunReport:
    report.status = status
    report.message = message
    report.finished_at = datetime.now(UTC)
    report.duration_ms = round((time.perf_counter() - t0) * 1000)
    return report


def _line(s: StepReport) -> str:
    if not s.result.ok:
        mark, why = "FAIL", f"action {s.result.error.code if s.result.error else 'failed'}"
    elif s.verification is None or not s.verification.verified:
        failures = s.verification.failures() if s.verification else []
        mark = "FAIL"
        why = "; ".join(f"{c.expected}: {c.detail}" for c in failures) or "not verified"
    else:
        mark, why = "ok  ", "+".join(s.verification.verification.method)
    return f"  {mark} {s.seq}. {s.instruction_text}  [{s.result.duration_ms} ms, {why}]"

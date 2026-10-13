"""`krama run`: plan → approve → execute → observe → verify, one task, one browser."""

import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig, page_snapshot
from app.agent.runlog import MASK, ScriptedStep, looks_sensitive, mask_expected, run_script
from app.contracts_gen.plan_schema import Plan, PlannedStep
from app.llm import LLMError
from app.planner import InvalidPlanError, NeedsClarificationError, Planner, PlanRequest
from app.ports.observer import Observer
from app.runs.report import ObservedSummary, RunReport, RunStatus, StepReport
from app.runs.steps import act_and_verify
from app.verifier import StepVerifier

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
    verifier: StepVerifier
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
                        page_snapshot=await page_snapshot(page),
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
    verifier: StepVerifier,
    options: RunOptions,
    page: Page,
) -> StepReport:
    out = await act_and_verify(
        step,
        executor,
        observer,
        verifier,
        page,
        verify_timeout_s=options.verify_timeout_s,
        verify_interval_s=options.verify_interval_s,
    )
    logged_action = step.action
    if step.action.value is not None and looks_sensitive(step.target.name):
        logged_action = step.action.model_copy(update={"value": MASK})
    return StepReport(
        seq=step.seq,
        instruction_text=step.instruction_text,
        action=logged_action,
        target=step.target,
        risk=step.risk,
        result=out.result,
        observed=ObservedSummary(
            url=out.observed.url, title=out.observed.title, screenshot_path=out.observed.screenshot_path
        ),
        verification=out.verification,
        verify_attempts=out.verify_attempts,
    )


def _masked(plan: Plan) -> Plan:
    steps = []
    for s in plan.steps:
        update: dict[str, Any] = {"expected_state": mask_expected(s.expected_state)}
        if s.action.value is not None and looks_sensitive(s.target.name):
            update["action"] = s.action.model_copy(update={"value": MASK})
        steps.append(s.model_copy(update=update))
    return plan.model_copy(update={"steps": steps})


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

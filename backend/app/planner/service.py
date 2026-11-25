"""Background planning for `POST /tasks` and `/tasks/{id}/clarify`: look at the target page, then plan.

The planner needs the start page's ARIA snapshot, so planning opens its own short browser session (signed in
first if the target needs it). The task moves `planning → planned | needs_clarification | failed`; nothing
is ever executed here.
"""

import asyncio
import logging
import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import (
    ActionExecutor,
    PlaywrightSession,
    SessionConfig,
    open_start_page,
    page_snapshot,
    start_path,
)
from app.agent.runlog import run_script
from app.db import PlanRow, TaskRow
from app.llm import LLMError, LLMRateLimitedError
from app.planner.planner import InvalidPlanError, NeedsClarificationError, Planner, PlanRequest
from app.ports.models import ObservedState
from app.ports.policy import Policy
from app.runs.profiles import ProfileStore
from app.runs.site_notes import site_notes
from app.targets import PrepareError, TargetSetup

logger = logging.getLogger(__name__)


class PlanningService:
    """At most `max_concurrent` plannings at once; each holds a browser for a few seconds."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        planner: Planner,
        target: Callable[[str], TargetSetup],
        *,
        session_config: Callable[[str], SessionConfig] = lambda url: SessionConfig(base_url=url),
        max_concurrent: int = 1,
        policy: Policy | None = None,
        profiles: ProfileStore | None = None,
    ) -> None:
        """`policy` masks secrets in the page snapshot before it goes to the LLM (#63). `profiles`: the
        owner's stored sign-ins (ADR 0012), so the planner sees the same signed-in page the run will."""
        self._sessions = sessions
        self._planner = planner
        self._target = target
        self._profiles = profiles
        self._session_config = session_config
        self._policy = policy
        self._slots = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def submit(self, task_id: UUID) -> None:
        """Plan in the background. Returns at once; the task row says how it went."""
        task = asyncio.create_task(self._guarded(task_id), name=f"plan-{task_id}")
        self._tasks[task_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(task_id, None))

    async def wait(self, task_id: UUID) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.cancelling():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _guarded(self, task_id: UUID) -> None:
        async with self._slots:
            try:
                await self._plan(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("planning task %s crashed", task_id)
                await self._finish(task_id, "failed", error=_error("internal", "Planning failed"))

    async def _plan(self, task_id: UUID) -> None:
        async with self._sessions() as s:
            task = await s.get(TaskRow, task_id)
            if task is None or task.status != "planning":
                return
            prompt, target_url, owner = task.prompt, task.target_url, task.user_id
        setup = self._target(target_url)
        if setup.anonymous_ok and self._profiles is not None and owner is not None:
            # Any other site (ADR 0012): plan on the page as the owner sees it, signed in when they stored a
            # sign-in, like the run's executor does. Signed out otherwise: most pages are public.
            profile = await self._profiles.load(owner, setup.site or "")
            if profile is not None:
                setup = replace(setup, storage_state=profile.state, signed_in_as=profile.account)
        if setup.sign_in_problem is not None:
            error = _error("internal", setup.sign_in_problem, "sign_in_required")
            await self._finish(task_id, "failed", error=error)
            return
        if setup.prepare is not None:
            try:
                await setup.prepare()
            except PrepareError as e:
                logger.warning("preparing %s for task %s failed: %s", target_url, task_id, e)
                message = "Couldn't set up the practice repository on the test account"
                await self._finish(task_id, "failed", error=_error("internal", message, "target_unavailable"))
                return
        config = self._session_config(target_url)
        config = setup.browser_config(config)

        async with PlaywrightSession(config) as session:
            page = session.page
            executor = ActionExecutor(page)
            if not await open_start_page(page, start_path(target_url)):
                error = _error("internal", f"Couldn't open {target_url}", "site_unreachable")
                await self._finish(task_id, "failed", error=error)
                return
            if setup.signed_in_check is not None and not await setup.signed_in_check(page):
                message = "The stored session no longer signs in. Log in again."
                await self._finish(task_id, "failed", error=_error("internal", message, "sign_in_required"))
                return
            if setup.preconditions:
                log = await run_script(
                    executor, setup.preconditions, task="preconditions", base_url=target_url
                )
                if not log.ok:
                    message = "Could not prepare the target site (sign-in failed)"
                    await self._finish(task_id, "failed", error=_error("internal", message))
                    return
            request = PlanRequest(
                task_id=task_id,
                task=prompt,
                start_path=self._mask(executor.current_path()),
                page_snapshot=self._mask(await page_snapshot(page)),
                site=setup.site,
                signed_in_as=setup.signed_in_as,
                practice_repo=setup.practice_repo,
                site_notes=await self._notes(owner, target_url),
                example_suffix=f"{secrets.randbelow(9000) + 1000}",
            )

        try:
            result = await self._planner.plan(request)
        except NeedsClarificationError as e:
            await self._finish(task_id, "needs_clarification", clarification_question=e.question)
            return
        except LLMRateLimitedError:
            await self._finish(task_id, "failed", error=_error("rate_limited", "The LLM is out of quota"))
            return
        except LLMError:
            await self._finish(task_id, "failed", error=_error("llm_unavailable", "The LLM is unavailable"))
            return
        except InvalidPlanError as e:
            await self._finish(task_id, "failed", error=_error("internal", f"No valid plan: {e}"))
            return

        plan = result.plan
        async with self._sessions.begin() as s:
            s.add(
                PlanRow(
                    id=plan.id,
                    task_id=task_id,
                    revision=plan.revision,
                    status=plan.status,
                    risk=plan.risk,
                    expected_result=plan.expected_result,
                    title=plan.title,
                    steps=[step.model_dump(mode="json", exclude_none=True) for step in plan.steps],
                    mode=plan.mode or "upfront",
                    outline=[o.model_dump(mode="json") for o in plan.outline] if plan.outline else None,
                )
            )
            task_row = await s.get(TaskRow, task_id)
            assert task_row is not None
            task_row.status, task_row.clarification_question, task_row.error = "planned", None, None

    async def _notes(self, owner: UUID | None, target_url: str) -> str | None:
        """The owner's site notes (#480), masked like other page text."""
        notes = await site_notes(self._sessions, owner, target_url)
        return self._mask(notes) if notes else None

    def _mask(self, text: str) -> str:
        """Page-derived text (snapshot, URL path) through the policy's mask before the LLM sees it."""
        if self._policy is None:
            return text
        state = ObservedState(url="/", title="", aria_excerpt=text, captured_at=datetime.now(UTC))
        return self._policy.mask(state).aria_excerpt

    async def _finish(self, task_id: UUID, status: str, **fields: Any) -> None:
        async with self._sessions.begin() as s:
            task = await s.get(TaskRow, task_id)
            if task is not None:
                task.status = status
                for name, value in fields.items():
                    setattr(task, name, value)


def _error(code: str, message: str, reason: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, **({"details": {"reason": reason}} if reason else {})}

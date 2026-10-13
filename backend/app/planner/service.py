"""Background planning for `POST /tasks` and `/tasks/{id}/clarify`: look at the target page, then plan.

The planner needs the start page's ARIA snapshot, so planning opens its own short browser session (signed in
first if the target needs it). The task moves `planning → planned | needs_clarification | failed`; nothing
is ever executed here.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig, page_snapshot
from app.agent.runlog import run_script
from app.db import PlanRow, TaskRow
from app.llm import LLMError, LLMRateLimitedError
from app.planner.planner import InvalidPlanError, NeedsClarificationError, Planner, PlanRequest
from app.targets import TargetSetup

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
    ) -> None:
        self._sessions = sessions
        self._planner = planner
        self._target = target
        self._session_config = session_config
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
            prompt, target_url = task.prompt, task.target_url
        setup = self._target(target_url)

        async with PlaywrightSession(self._session_config(target_url)) as session:
            page = session.page
            executor = ActionExecutor(page)
            await page.goto("/", wait_until="domcontentloaded")
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
                start_path=executor.current_path(),
                page_snapshot=await page_snapshot(page),
                site=setup.site,
                signed_in_as=setup.signed_in_as,
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
                    steps=[step.model_dump(mode="json", exclude_none=True) for step in plan.steps],
                )
            )
            task_row = await s.get(TaskRow, task_id)
            assert task_row is not None
            task_row.status, task_row.clarification_question, task_row.error = "planned", None, None

    async def _finish(self, task_id: UUID, status: str, **fields: Any) -> None:
        async with self._sessions.begin() as s:
            task = await s.get(TaskRow, task_id)
            if task is not None:
                task.status = status
                for name, value in fields.items():
                    setattr(task, name, value)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message}

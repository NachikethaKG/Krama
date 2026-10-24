"""The Phase 1 API end to end: task → plan → edit → approve → live events → stored workflow.

Real Postgres, real Chromium, real observer and verifier on a real local site, through the real FastAPI app
(lifespan included). Only the LLM is the recorded fake.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.accounts import SessionLimits, create_user, start_session
from app.api.services import Services
from app.contracts_gen.events_schema import RunEvent
from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.run_schema import Run, RunPage
from app.contracts_gen.task_schema import Task
from app.contracts_gen.workflow_schema import Workflow, WorkflowPage
from app.db import PlanRow, RunRow, TaskRow, UserRow
from app.llm import FakeProvider, FakeResponse
from app.main import create_app
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.planner.service import PlanningService
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.events import EventHub
from app.storage import LocalFsStore, get_artifact_store
from app.targets import TargetSetup
from app.verifier import LayeredVerifier
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = pytest.mark.anyio

Sessions = async_sessionmaker[AsyncSession]
EVENTS: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)
CLARIFY = {"expected_result": "", "steps": [], "clarification_question": "Which name should the item get?"}
NEVER = step(2, {"type": "wait"}, {"role": "button", "name": "Never appears"}, "Wait.", {"url_matches": "/"})


def services(sessions: Sessions, tmp_path: Path, *replies: FakeResponse) -> Services:
    hub = EventHub()
    store = RunStore(sessions, on_event=hub.notify)
    env = RunEnvironment(
        verifier=LayeredVerifier(),
        observer_for=lambda run_id: PageObserver(artifacts_dir=tmp_path / "runs" / str(run_id)),
        artifacts_dir=tmp_path,
    )
    planner = LLMPlanner(FakeProvider(list(replies)), max_attempts=1)
    return Services(
        sessions=sessions,
        hub=hub,
        store=store,
        executor=InProcessExecutor(store, env),
        planning=PlanningService(sessions, planner, lambda _url: TargetSetup()),
    )


def reply(response: dict[str, Any], *, when: list[str] | None = None, name: str = "plan") -> FakeResponse:
    return FakeResponse(name=name, schema_name="LLMPlan", prompt_contains=when or [], response=response)


async def make_user(sessions: Sessions, email: str | None = None) -> UserRow:
    async with sessions.begin() as s:
        return await create_user(s, email or f"user-{uuid4().hex[:8]}@krama.test", "a long test password 123")


class Api:
    """The app with its lifespan running, plus an httpx client that talks to it in-process, signed in as
    `user` (a new account unless given) with the X-Krama header every change needs (#94)."""

    def __init__(self, svc: Services, user: UserRow | None = None) -> None:
        self.svc = svc
        self.user = user
        self.app = create_app(svc)
        root = svc.executor.artifacts_dir
        self.app.dependency_overrides[get_artifact_store] = lambda: LocalFsStore(root)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test/api/v1", timeout=120
        )

    async def __aenter__(self) -> "Api":
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()
        self.user = self.user or await make_user(self.svc.sessions)
        async with self.svc.sessions.begin() as s:
            token = await start_session(s, self.user, SessionLimits())
        self.client.cookies.set("krama_session", token)
        self.client.headers["X-Krama"] = "1"
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.client.aclose()
        await self._lifespan.__aexit__(None, None, None)

    async def planned_task(self, site: str) -> Task:
        created = await self.client.post(
            "/tasks", json={"prompt": "Create the item demo-item", "target_url": site}
        )
        assert created.status_code == 202, created.text
        task = Task.model_validate(created.json())
        assert task.status == "planning"
        await self.svc.planning.wait(task.id)
        return Task.model_validate((await self.client.get(f"/tasks/{task.id}")).json())

    async def events(self, run_id: UUID, last_event_id: int | None = None) -> list[dict[str, Any]]:
        headers = {"Last-Event-ID": str(last_event_id)} if last_event_id is not None else {}
        response = await self.client.get(f"/runs/{run_id}/events", headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        return parse_sse(response.text)


def parse_sse(body: str) -> list[dict[str, Any]]:
    """Wire format → events, checking that `id:` and `event:` agree with the data."""
    out = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if not fields:
            continue  # a keep-alive comment
        data = json.loads(fields["data"])
        EVENTS.validate_python(data)
        assert (fields["id"], fields["event"]) == (str(data["seq"]), data["type"])
        out.append(data)
    return out


async def test_task_to_verified_workflow(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        c = api.client
        task = await api.planned_task(site)
        assert task.status == "planned" and task.plan_id is not None

        plan = Plan.model_validate((await c.get(f"/plans/{task.plan_id}")).json())
        assert (plan.revision, plan.status, len(plan.steps)) == (1, "proposed", 4)

        # Edit: drop the README step and reword step 1. Revision goes to 2, risk is recomputed.
        steps = [s.model_dump(mode="json", exclude_none=True) for s in plan.steps]
        steps[0]["instruction_text"] = "Open the New item form."
        edited = await c.patch(
            f"/plans/{plan.id}", json={"revision": 1, "steps": [steps[0], steps[1], steps[3]]}
        )
        assert edited.status_code == 200, edited.text
        plan = Plan.model_validate(edited.json())
        assert plan.revision == 2 and [s.seq for s in plan.steps] == [1, 2, 3]

        stale = await c.post(f"/plans/{plan.id}/approve", json={"revision": 1})
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "conflict"

        approved = await c.post(f"/plans/{plan.id}/approve", json={"revision": 2})
        assert approved.status_code == 201, approved.text
        run = Run.model_validate(approved.json())
        assert (run.status, run.plan_revision) == ("queued", 2)

        # Live: connects while the run is still going and ends at the final event.
        stream = await api.events(run.id)
        assert [e["type"] for e in stream] == [
            "run.started",
            *["step.started", "step.action_done", "step.verified"] * 3,
            "run.completed",
        ]
        assert stream[3]["method"] and stream[2]["screenshot_url"].startswith("/api/v1/artifacts/runs/")
        shot = await c.get(stream[2]["screenshot_url"].removeprefix("/api/v1"))
        assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"

        run = Run.model_validate((await c.get(f"/runs/{run.id}")).json())
        assert run.status == "verified" and run.workflow_id == UUID(stream[-1]["workflow_id"])

        workflow = Workflow.model_validate((await c.get(f"/workflows/{run.workflow_id}")).json())
        assert workflow.status == "verified" and workflow.task == "Create the item demo-item"
        assert workflow.steps[0].instruction_text == "Open the New item form."
        assert all(s.verification.result == "verified" for s in workflow.steps)

        # The text guide (#79): the same step texts, numbered, each with a screenshot that really downloads.
        guide = await c.get(f"/workflows/{run.workflow_id}/guide.md")
        assert guide.status_code == 200 and guide.headers["content-type"].startswith("text/markdown")
        numbered = [line for line in guide.text.splitlines() if line[:1].isdigit()]
        assert numbered == [f"{i}. {s.instruction_text}" for i, s in enumerate(workflow.steps, start=1)]
        images = re.findall(r"!\[Step \d+\]\((http://test/api/v1/artifacts/[^)]+)\)", guide.text)
        assert len(images) == 3
        shot = await c.get(images[0].removeprefix("http://test/api/v1"))
        assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"

        page = WorkflowPage.model_validate((await c.get("/workflows", params={"target_app": "gitea"})).json())
        assert [w.id for w in page.items] == [workflow.id] and page.items[0].step_count == 3
        runs = RunPage.model_validate((await c.get("/runs")).json())
        assert [r.id for r in runs.items] == [run.id] and runs.next_cursor is None

        resumed = await api.events(run.id, last_event_id=8)  # EventSource reconnecting after seq 8
        assert [e["seq"] for e in resumed] == [9, 10, 11]


async def test_the_planner_can_ask_first(sessions: Sessions, tmp_path: Path, site: str) -> None:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN, when=["A: demo-item"]), reply(CLARIFY, name="ask"))
    async with Api(svc) as api:
        task = await api.planned_task(site)
        assert task.status == "needs_clarification"
        assert task.clarification_question == "Which name should the item get?" and task.plan_id is None

        answered = await api.client.post(f"/tasks/{task.id}/clarify", json={"answer": "demo-item"})
        assert answered.status_code == 202 and answered.json()["status"] == "planning"
        await svc.planning.wait(task.id)

        task = Task.model_validate((await api.client.get(f"/tasks/{task.id}")).json())
        assert task.status == "planned" and task.plan_id is not None
        again = await api.client.post(f"/tasks/{task.id}/clarify", json={"answer": "x"})
        assert again.status_code == 409


async def test_planning_without_an_llm_answer_fails_the_task(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path)) as api:  # the fake LLM has no reply at all
        task = await api.planned_task(site)

    assert task.status == "failed" and task.error is not None
    assert task.error.code == "llm_unavailable"


async def test_plan_edits_are_checked(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        c = api.client
        plan_id = (await api.planned_task(site)).plan_id
        plan = Plan.model_validate((await c.get(f"/plans/{plan_id}")).json())
        broken = plan.steps[0].model_dump(mode="json", exclude_none=True)
        broken["expected_state"] = {"url_matches": "https://evil.example/"}

        bad = await c.patch(f"/plans/{plan_id}", json={"revision": 1, "steps": [broken]})
        assert bad.status_code == 422
        assert "not a full URL" in json.dumps(bad.json()["error"]["details"]["problems"])

        rejected = await c.post(f"/plans/{plan_id}/reject", json={"reason": "not now"})
        assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
        steps = [s.model_dump(mode="json", exclude_none=True) for s in plan.steps]
        frozen = await c.patch(f"/plans/{plan_id}", json={"revision": 1, "steps": steps})
        assert frozen.status_code == 409 and frozen.json()["error"]["code"] == "plan_not_editable"
        late = await c.post(f"/plans/{plan_id}/approve", json={"revision": 1})
        assert late.status_code == 409 and late.json()["error"]["code"] == "plan_not_editable"


async def test_cancel_a_running_run(sessions: Sessions, tmp_path: Path, site: str) -> None:
    waiting_plan = {**GOOD_PLAN, "steps": [GOOD_PLAN["steps"][0], NEVER]}
    async with Api(services(sessions, tmp_path, reply(waiting_plan))) as api:
        c = api.client
        plan_id = (await api.planned_task(site)).plan_id
        run_id = (await c.post(f"/plans/{plan_id}/approve", json={"revision": 1})).json()["id"]
        stream = asyncio.create_task(api.events(UUID(run_id)))
        for _ in range(200):
            if (await c.get(f"/runs/{run_id}")).json()["current_seq"] == 2:
                break
            await asyncio.sleep(0.05)

        cancelled = await c.post(f"/runs/{run_id}/cancel")
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        events = await asyncio.wait_for(stream, timeout=10)  # the open stream ends with the cancel
        assert events[-1]["type"] == "run.cancelled" and events[-1]["step_seq"] == 2
        again = await c.post(f"/runs/{run_id}/cancel")
        assert again.status_code == 409 and again.json()["error"]["code"] == "run_not_active"


async def test_unknown_ids_and_bad_input(sessions: Sessions, tmp_path: Path) -> None:
    unknown = "6f1c2a4e-1111-4b8a-9a1b-123456789abc"
    async with Api(services(sessions, tmp_path)) as api:
        c = api.client
        for path in (f"/tasks/{unknown}", f"/plans/{unknown}", f"/runs/{unknown}", f"/workflows/{unknown}",
                     f"/workflows/{unknown}/guide.md", f"/runs/{unknown}/events"):  # fmt: skip
            response = await c.get(path)
            assert response.status_code == 404 and response.json()["error"]["code"] == "not_found", path
        assert (await c.post(f"/runs/{unknown}/cancel")).status_code == 404
        assert (await c.get("/runs", params={"cursor": "not-a-cursor"})).status_code == 422
        assert (await c.get("/runs", params={"limit": 0})).status_code == 422
        assert (await c.post("/tasks", json={"prompt": "", "target_url": "x"})).status_code == 422


async def test_startup_fails_runs_a_restart_interrupted(sessions: Sessions, tmp_path: Path) -> None:
    user = await make_user(sessions)
    async with sessions.begin() as s:
        task = TaskRow(user_id=user.id, prompt="p", target_url="http://127.0.0.1:1", status="planned")
        s.add(task)
        await s.flush()
        plan = PlanRow(task_id=task.id, risk="low", expected_result="r", steps=[GOOD_PLAN["steps"][0]])
        s.add(plan)
        await s.flush()
        run = RunRow(plan_id=plan.id, plan_revision=1, status="running")
        s.add(run)

    async with Api(services(sessions, tmp_path), user) as api:
        after = Run.model_validate((await api.client.get(f"/runs/{run.id}")).json())

    assert after.status == "failed" and after.error is not None
    assert after.error.details == {"reason": "interrupted"}


async def test_confirm_answers_a_paused_run(sessions: Sessions, tmp_path: Path, site: str) -> None:
    risky = {**GOOD_PLAN, "steps": [*GOOD_PLAN["steps"][:3], {**GOOD_PLAN["steps"][3], "risk": "high"}]}
    async with Api(services(sessions, tmp_path, reply(risky))) as api:
        c = api.client
        plan_id = (await api.planned_task(site)).plan_id
        run_id = (await c.post(f"/plans/{plan_id}/approve", json={"revision": 1})).json()["id"]
        for _ in range(400):
            run = (await c.get(f"/runs/{run_id}")).json()
            if run["status"] == "paused":
                break
            await asyncio.sleep(0.05)
        assert (run["status"], run["current_seq"]) == ("paused", 4)

        wrong = await c.post(f"/runs/{run_id}/confirm", json={"step_seq": 3, "decision": "allow"})
        assert wrong.status_code == 409 and wrong.json()["error"]["code"] == "run_not_active"
        allowed = await c.post(f"/runs/{run_id}/confirm", json={"step_seq": 4, "decision": "allow"})
        assert allowed.status_code == 200 and allowed.json()["status"] == "running"

        stream = await api.events(UUID(run_id))
        types = [e["type"] for e in stream]
        assert types[types.index("run.paused") + 1] == "run.resumed" and types[-1] == "run.completed"
        late = await c.post(f"/runs/{run_id}/confirm", json={"step_seq": 4, "decision": "deny"})
        assert late.status_code == 409
        unknown = await c.post(f"/runs/{uuid4()}/confirm", json={"step_seq": 1, "decision": "allow"})
        assert unknown.status_code == 404

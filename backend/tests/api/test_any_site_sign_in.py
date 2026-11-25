"""Sign in to any site (ADR 0012, #475-#478): by URL, with the generic "who is signed in?" check, and
sensitive sites refused. The local test site stands in for an unknown site: no per-site code is involved."""

from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.contracts_gen.run_schema import Run
from app.contracts_gen.site_schema import SiteProfileList
from app.contracts_gen.takeover_schema import TakeoverKey, TakeoverText
from app.contracts_gen.task_schema import Task
from app.planner.planner import NeedsClarificationError, PlanRequest, PlanResult
from app.planner.service import PlanningService
from app.runs import InProcessExecutor
from app.runs.profiles import ProfileStore
from app.targets import target_setup
from tests.api.test_flow import Api, Sessions, services
from tests.api.test_takeover_flow import click, wait_status

pytestmark = pytest.mark.anyio

SETTINGS = Settings(_env_file=None)


def any_site_services(sessions: Sessions, tmp_path: Path) -> Any:
    store = ProfileStore(sessions, Fernet.generate_key().decode())
    svc = services(sessions, tmp_path, profiles=store)
    svc.profiles = store
    svc.target = lambda url: target_setup(url, SETTINGS)
    svc.executor._env.target = lambda job: target_setup(job.target_url, SETTINGS)  # type: ignore[union-attr]
    return svc


async def test_signing_in_to_any_site_by_url(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(any_site_services(sessions, tmp_path)) as api:
        started = await api.client.post("/sites/sign-in", json={"url": f"{site}/signin", "terms_ok": True})
        assert started.status_code == 202, started.text
        run_id = Run.model_validate(started.json()).id
        paused = await wait_status(api, run_id, "paused")
        assert paused.kind == "sign_in"

        assert (await api.client.post(f"/runs/{run_id}/takeover")).status_code == 200
        executor = api.svc.executor
        assert isinstance(executor, InProcessExecutor)
        session = executor.takeover(run_id)
        assert session is not None
        await click(api, run_id, "input[name=email]")
        await session.handle(TakeoverText(type="text", text="owner@example.com"))
        await click(api, run_id, "input[name=pw]")
        await session.handle(TakeoverText(type="text", text="typed by the owner only"))
        await session.handle(TakeoverKey(type="key", event="down", key="Enter"))
        await executor._takeover_pages[run_id].page.wait_for_url("**/account**")
        handed = await api.client.post(f"/runs/{run_id}/handback", json={"step_seq": 1, "done": "barrier"})
        assert handed.status_code == 200, handed.text
        stream = await api.events(run_id)
        profiles = SiteProfileList.model_validate((await api.client.get("/sites/profiles")).json())
        forgot = await api.client.delete("/sites/profile", params={"site": site})
        after = SiteProfileList.model_validate((await api.client.get("/sites/profiles")).json())

    assert stream[-1]["type"] == "run.completed"
    host = site.removeprefix("http://")
    assert [(p.site, p.account) for p in profiles.items] == [(site, f"your account on {host}")]
    assert "typed by the owner only" not in str(stream)
    assert forgot.status_code == 204 and after.items == []


async def test_without_a_session_cookie_it_is_not_signed_in(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    # Handing back on the sign-in form itself: no new session cookie, password field still there.
    async with Api(any_site_services(sessions, tmp_path)) as api:
        started = await api.client.post("/sites/sign-in", json={"url": f"{site}/signin", "terms_ok": True})
        run_id = Run.model_validate(started.json()).id
        await wait_status(api, run_id, "paused")
        assert (await api.client.post(f"/runs/{run_id}/takeover")).status_code == 200
        handed = await api.client.post(f"/runs/{run_id}/handback", json={"step_seq": 1, "done": "barrier"})
        assert handed.status_code == 200, handed.text
        again = await wait_status(api, run_id, "paused")
        profiles = SiteProfileList.model_validate((await api.client.get("/sites/profiles")).json())
        await api.client.post(f"/runs/{run_id}/cancel")

    assert again.status == "paused" and profiles.items == []


class AskingPlanner:
    """Keeps what the planner was given, then asks a question (the task ends needs_clarification)."""

    def __init__(self) -> None:
        self.requests: list[PlanRequest] = []

    async def plan(self, request: PlanRequest) -> PlanResult:
        self.requests.append(request)
        raise NeedsClarificationError("seen")


@pytest.mark.parametrize("stored", [True, False])
async def test_planning_sees_the_page_with_the_owners_sign_in(
    sessions: Sessions, tmp_path: Path, site: str, stored: bool
) -> None:
    # #482: the planner saw Trello signed out and asked to log in, though the owner had signed in on /sites.
    svc = any_site_services(sessions, tmp_path)
    planner = AskingPlanner()
    svc.planning = PlanningService(
        sessions, planner, lambda url: target_setup(url, SETTINGS), profiles=svc.profiles
    )
    async with Api(svc) as api:
        assert api.user is not None
        if stored:
            host = site.removeprefix("http://").split(":")[0]
            cookie = {"name": "sessionid", "value": "x", "domain": host, "path": "/", "expires": -1,
                      "httpOnly": True, "secure": False, "sameSite": "Lax"}  # fmt: skip
            state = {"cookies": [cookie], "origins": []}
            await svc.profiles.save(api.user.id, site, "your account", state)
        created = await api.client.post(
            "/tasks", json={"prompt": "Create a board", "target_url": f"{site}/dashboard"}
        )
        assert created.status_code == 202, created.text
        await svc.planning.wait(Task.model_validate(created.json()).id)

    [request] = planner.requests
    if stored:
        assert "Your boards" in request.page_snapshot
        assert request.signed_in_as == "your account"
    else:
        assert "Log in to see your boards" in request.page_snapshot
        assert request.signed_in_as is None


@pytest.mark.parametrize("url", ["https://www.paypal.com/signin", "https://netbanking.example-bank.com/"])
async def test_sensitive_sites_are_refused(sessions: Sessions, tmp_path: Path, url: str) -> None:
    async with Api(any_site_services(sessions, tmp_path)) as api:
        sign_in = await api.client.post("/sites/sign-in", json={"url": url, "terms_ok": True})
        task = await api.client.post("/tasks", json={"prompt": "Check my balance", "target_url": url})

    for response in (sign_in, task):
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"]["reason"] == "sensitive_site"


async def test_terms_must_be_confirmed(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(any_site_services(sessions, tmp_path)) as api:
        response = await api.client.post("/sites/sign-in", json={"url": f"{site}/signin", "terms_ok": False})

    assert response.status_code == 422

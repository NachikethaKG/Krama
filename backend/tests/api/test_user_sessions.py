"""Per-user site sessions (#404, ADR 0007): the encrypted profile store, sign-in runs taken over by hand, and
"Do it for me" acting in the user's own account. Real Postgres and Chromium on the local test site."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from playwright.async_api import Page
from sqlalchemy import update

from app.contracts_gen.run_schema import Run
from app.contracts_gen.site_schema import SiteProfileList
from app.contracts_gen.takeover_schema import TakeoverKey, TakeoverText
from app.contracts_gen.workflow_schema import WorkflowInputList
from app.db import BrowserProfileRow
from app.runs.do_it import swap_account
from app.runs.executor import InProcessExecutor
from app.runs.profiles import ProfileStore
from app.targets import TargetSetup
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.api.test_reverify import verified_workflow
from tests.api.test_takeover_flow import click, wait_status
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio

KEY = Fernet.generate_key().decode()
STATE: dict[str, Any] = {"cookies": [{"name": "sid", "value": "s3cret", "domain": "127.0.0.1", "path": "/",
                                      "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax"}],
                         "origins": []}  # fmt: skip


async def account_of(page: Page, state: Any) -> str | None:
    """The test site's 'who am I': signed in once the members page is open."""
    return "demo" if "/members" in page.url else None


def local_site() -> TargetSetup:
    return TargetSetup(site="local", login_path="/wall", account_of=account_of, signed_in_as="krama-bot")


def svc_with_profiles(sessions: Sessions, tmp_path: Path, site: str, *replies: Any) -> Any:
    store = ProfileStore(sessions, KEY)
    svc = services(sessions, tmp_path, *replies, profiles=store, target=local_site())
    svc.profiles, svc.sites = store, {"local": site}
    svc.target = lambda _url: local_site()
    svc.executor._env.target = lambda _job: local_site()  # type: ignore[union-attr]
    return svc


# --- the store


async def test_profiles_are_encrypted_per_user_and_site_and_expire(sessions: Sessions) -> None:
    store = ProfileStore(sessions, KEY)
    alice, bob = await make_user(sessions), await make_user(sessions)

    await store.save(alice.id, "github", "alice", STATE)
    async with sessions() as s:
        row = await s.get(BrowserProfileRow, (await store.list(alice.id))[0].id)
        assert row is not None and b"s3cret" not in row.state  # never stored in the clear

    profile = await store.load(alice.id, "github")
    assert profile is not None and profile.account == "alice" and profile.state == STATE
    assert await store.load(bob.id, "github") is None
    assert await ProfileStore(sessions, Fernet.generate_key().decode()).load(alice.id, "github") is None

    async with sessions.begin() as s:
        await s.execute(update(BrowserProfileRow).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    assert await store.load(alice.id, "github") is None
    assert await store.delete(alice.id, "github") is True


def test_the_recording_account_is_swapped_only_as_a_path_segment() -> None:
    planned = [
        {"action": {"type": "navigate", "value": "/demo/settings"}, "instruction_text": "Open demo-repo.",
         "expected_state": {"url_matches": "^/demo/demo-repo$", "title_contains": "demo/demo-repo"}},
    ]  # fmt: skip

    [step] = swap_account(planned, "demo", "alice")

    assert step["action"]["value"] == "/alice/settings"
    assert step["expected_state"]["url_matches"] == "^/alice/demo-repo$"
    assert step["expected_state"]["title_contains"] == "alice/demo-repo"
    assert step["instruction_text"] == "Open demo-repo."


# --- signing in by hand


async def test_a_sign_in_run_stores_the_users_session(sessions: Sessions, tmp_path: Path, site: str) -> None:
    svc = svc_with_profiles(sessions, tmp_path, site, reply(GOOD_PLAN))
    async with Api(svc) as api:
        started = await api.client.post("/sites/local/sign-in")
        assert started.status_code == 202, started.text
        run_id = Run.model_validate(started.json()).id
        paused = await wait_status(api, run_id, "paused")
        assert paused.kind == "sign_in"

        assert (await api.client.post(f"/runs/{run_id}/takeover")).status_code == 200
        executor = api.svc.executor
        assert isinstance(executor, InProcessExecutor)
        session = executor.takeover(run_id)
        assert session is not None
        await click(api, run_id, "input[name=user]")
        await session.handle(TakeoverText(type="text", text="demo"))
        await click(api, run_id, "input[name=pw]")
        await session.handle(TakeoverText(type="text", text="typed by the owner only"))
        await session.handle(TakeoverKey(type="key", event="down", key="Enter"))
        await executor._takeover_pages[run_id].page.wait_for_url("**/members**")
        handed = await api.client.post(f"/runs/{run_id}/handback", json={"step_seq": 1, "done": "barrier"})
        assert handed.status_code == 200, handed.text
        stream = await api.events(run_id)
        profiles = SiteProfileList.model_validate((await api.client.get("/sites/profiles")).json())
        unknown = await api.client.post("/sites/nowhere/sign-in")

    assert stream[-1]["type"] == "run.completed" and "workflow_id" not in stream[-1]
    assert [(p.site, p.account) for p in profiles.items] == [("local", "demo")]
    assert "typed by the owner only" not in str(stream)
    assert unknown.status_code == 404


async def test_a_paused_sign_in_run_answers_allow_and_deny(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    # It paused with no current step, so both buttons on the pause answered 409 (#431 gate).
    svc = svc_with_profiles(sessions, tmp_path, site, reply(GOOD_PLAN))
    async with Api(svc) as api:
        run_id = Run.model_validate((await api.client.post("/sites/local/sign-in")).json()).id
        paused = await wait_status(api, run_id, "paused")
        allowed = await api.client.post(f"/runs/{run_id}/confirm", json={"step_seq": 1, "decision": "allow"})
        again = await wait_status(api, run_id, "paused")  # nobody signed in: it asks again
        denied = await api.client.post(f"/runs/{run_id}/confirm", json={"step_seq": 1, "decision": "deny"})
        stream = await api.events(run_id)

    assert paused.current_seq == 1
    assert allowed.status_code == 200, allowed.text
    assert again.current_seq == 1
    assert denied.status_code == 200, denied.text
    assert any("can't see that you're signed in" in str(e) for e in stream)
    assert stream[-1]["type"] == "run.cancelled"


# --- do it for me in the user's own account


async def test_do_it_needs_the_users_own_session_and_then_acts_in_it(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    svc = svc_with_profiles(sessions, tmp_path, site, reply(GOOD_PLAN))
    async with Api(svc) as api:
        assert api.user is not None
        workflow_id = await verified_workflow(api, site)
        before = WorkflowInputList.model_validate(
            (await api.client.get(f"/workflows/{workflow_id}/inputs")).json()
        )
        body = {"revision": 1, "inputs": {"item_name": "team-notes"}}
        refused = await api.client.post(f"/workflows/{workflow_id}/run", json=body)

        await svc.profiles.save(api.user.id, "local", "demo", STATE)
        after = WorkflowInputList.model_validate(
            (await api.client.get(f"/workflows/{workflow_id}/inputs")).json()
        )
        ran = await api.client.post(f"/workflows/{workflow_id}/run", json=body)
        assert ran.status_code == 202, ran.text
        run_id = Run.model_validate(ran.json()).id
        stream = await api.events(run_id)
        signed_out = await api.client.delete("/sites/local/profile")
        gone = SiteProfileList.model_validate((await api.client.get("/sites/profiles")).json())

    assert (before.account, before.sign_in_site) == (None, "local")
    assert refused.status_code == 409
    assert refused.json()["error"]["details"] == {"reason": "site_sign_in_needed", "site": "local"}
    assert (after.account, after.sign_in_site) == ("demo", None)
    assert stream[-1]["type"] == "run.completed", stream[-1]
    assert signed_out.status_code == 204 and gone.items == []


async def test_versions_remember_the_account_they_were_recorded_in(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN))
    svc.executor._env.target = lambda _job: local_site()  # type: ignore[union-attr]
    async with Api(svc) as api:
        workflow_id = await verified_workflow(api, site)
        versions = (await api.client.get(f"/workflows/{workflow_id}/versions")).json()

    assert versions["items"][0]["recorded_as"] == "krama-bot"

"""Accounts, sessions, CSRF and ownership (#94), through the real app and Postgres."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, update

from app.api import auth
from app.api.accounts import (
    FREE_FAILURES,
    PasswordRuleError,
    SessionLimits,
    hash_password,
    session_user,
    start_session,
    token_hash,
)
from app.contracts_gen.task_schema import Task
from app.contracts_gen.workflow_schema import WorkflowPage
from app.db import SessionRow, TaskRow, UserRow
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio

PASSWORD = "a long test password 123"


@pytest.fixture(autouse=True)
def fresh_ip_limit() -> None:
    auth._attempts.clear()


def anonymous(api: Api) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api.app), base_url="http://test/api/v1", headers={"X-Krama": "1"}
    )


# --- sign in / out ---


async def test_login_sets_an_http_only_cookie_and_me_answers(sessions: Sessions, tmp_path: Path) -> None:
    user = await make_user(sessions, f"Mixed.Case-{uuid4().hex[:6]}@Krama.test")
    async with Api(services(sessions, tmp_path)) as api, anonymous(api) as c:
        response = await c.post("/auth/login", json={"email": user.email.upper(), "password": PASSWORD})

        assert response.status_code == 200, response.text
        assert response.json()["email"] == user.email and "password" not in response.text
        cookie = response.headers["set-cookie"].lower()
        assert "krama_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
        me = await c.get("/auth/me")
        assert me.status_code == 200 and me.json()["id"] == str(user.id)


async def test_a_wrong_password_and_an_unknown_email_get_the_same_answer(
    sessions: Sessions, tmp_path: Path
) -> None:
    user = await make_user(sessions)
    async with Api(services(sessions, tmp_path)) as api, anonymous(api) as c:
        wrong = await c.post("/auth/login", json={"email": user.email, "password": "not the password at all"})
        unknown = await c.post("/auth/login", json={"email": "nobody@krama.test", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert (
        wrong.json()
        == unknown.json()
        == {"error": {"code": "unauthorized", "message": "Wrong email or password"}}
    )
    assert "set-cookie" not in wrong.headers


async def test_logout_revokes_the_session_on_the_server(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        token = api.client.cookies["krama_session"]
        assert (await api.client.post("/auth/logout")).status_code == 204

        async with anonymous(api) as c:
            c.cookies.set("krama_session", token)  # someone kept the old cookie
            assert (await c.get("/auth/me")).status_code == 401
    async with sessions() as s:
        row = await s.scalar(select(SessionRow).where(SessionRow.token_hash == token_hash(token)))
        assert row is not None and row.revoked_at is not None


async def test_the_database_never_holds_the_cookie_token(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        token = api.client.cookies["krama_session"]
    async with sessions() as s:
        stored = (await s.scalars(select(SessionRow.token_hash))).all()
    assert token not in stored and token_hash(token) in stored


async def test_repeated_failures_make_the_account_wait(sessions: Sessions, tmp_path: Path) -> None:
    user = await make_user(sessions)
    async with Api(services(sessions, tmp_path)) as api, anonymous(api) as c:
        for _ in range(FREE_FAILURES):
            await c.post("/auth/login", json={"email": user.email, "password": "wrong wrong wrong"})
        await c.post("/auth/login", json={"email": user.email, "password": "wrong wrong wrong"})

        blocked = await c.post("/auth/login", json={"email": user.email, "password": PASSWORD})

    assert blocked.status_code == 429 and blocked.json()["error"]["details"]["retry_after_s"] >= 1


async def test_one_ip_is_limited_across_accounts(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api, anonymous(api) as c:
        codes = [
            (
                await c.post("/auth/login", json={"email": f"x{i}@krama.test", "password": "nope nope nope"})
            ).status_code
            for i in range(auth.IP_ATTEMPTS + 1)
        ]
    assert codes[:-1] == [401] * auth.IP_ATTEMPTS and codes[-1] == 429


def test_passwords_need_fifteen_characters() -> None:
    with pytest.raises(PasswordRuleError):
        hash_password("too short")
    assert hash_password("x" * 15).startswith("$argon2id$")


async def test_sessions_end_when_idle_or_too_old(sessions: Sessions) -> None:
    user = await make_user(sessions)
    limits = SessionLimits(idle=timedelta(days=7), absolute=timedelta(days=30))
    t0 = datetime.now(UTC)
    async with sessions.begin() as s:
        token = await start_session(s, user, limits, now=t0)
    async with sessions.begin() as s:
        assert (
            await session_user(s, token, limits, now=t0 + timedelta(days=6)) is not None
        )  # touches last_seen
        assert await session_user(s, token, limits, now=t0 + timedelta(days=12)) is not None  # 6 days idle
        assert await session_user(s, token, limits, now=t0 + timedelta(days=20)) is None  # 8 days idle
    async with sessions.begin() as s:
        await s.execute(update(SessionRow).values(last_seen_at=t0 + timedelta(days=29)))
        assert (
            await session_user(s, token, limits, now=t0 + timedelta(days=30, minutes=1)) is None
        )  # absolute


# --- CSRF ---


@pytest.mark.parametrize(
    ("headers", "allowed"),
    [
        ({"X-Krama": "1", "Origin": "http://localhost:3000"}, True),
        ({"X-Krama": "1"}, True),  # server-side calls from Next.js send no Origin
        ({}, False),  # no custom header: what a forged form or <img> would send
        ({"X-Krama": "1", "Origin": "http://evil.test"}, False),
        ({"X-Krama": "1", "Origin": "http://localhost:4000"}, False),  # same site, other port
        ({"X-Krama": "1", "Sec-Fetch-Site": "cross-site"}, False),
    ],
)
async def test_csrf_rules_on_changes(
    sessions: Sessions, tmp_path: Path, headers: dict[str, str], allowed: bool
) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        del api.client.headers["X-Krama"]
        response = await api.client.post("/auth/logout", headers=headers)

    assert response.status_code == (204 if allowed else 403), response.text
    if not allowed:
        assert response.json()["error"]["code"] == "forbidden"


async def test_a_form_encoded_body_is_refused(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        response = await api.client.post("/tasks", content="prompt=x", headers={"Content-Type": "text/plain"})

    assert response.status_code == 403


async def test_reads_need_no_csrf_header_but_do_need_a_session(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        del api.client.headers["X-Krama"]
        assert (await api.client.get("/workflows")).status_code == 200
        async with anonymous(api) as c:
            for path in (
                "/workflows",
                "/runs",
                "/auth/me",
                f"/tasks/{uuid4()}",
                f"/artifacts/runs/{uuid4()}/x.png",
            ):
                response = await c.get(path)
                assert response.status_code == 401 and response.json()["error"]["code"] == "unauthorized", (
                    path
                )
        assert (await api.client.get("/health")).status_code == 200


# --- ownership ---


async def test_users_only_see_their_own_tasks_runs_workflows_and_files(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN))
    alice, bob = await make_user(sessions), await make_user(sessions)
    async with Api(svc, alice) as a:
        task = await a.planned_task(site)
        assert task.plan_id is not None
        plan = (await a.client.get(f"/plans/{task.plan_id}")).json()
        run = (
            await a.client.post(f"/plans/{plan['id']}/approve", json={"revision": plan["revision"]})
        ).json()
        await svc.executor.wait(UUID(run["id"]))
        workflows = WorkflowPage.model_validate((await a.client.get("/workflows")).json())
        assert len(workflows.items) == 1
        workflow_id = workflows.items[0].id
        shot = (await a.client.get(f"/workflows/{workflow_id}")).json()["steps"][0]["screenshot_path"]
        assert (await a.client.get(f"/artifacts/{shot}")).status_code == 200

    async with sessions() as s:
        stored = await s.get(TaskRow, task.id)
        assert stored is not None and stored.user_id == alice.id

    async with Api(svc, bob) as b:
        for path in (
            f"/tasks/{task.id}",
            f"/plans/{plan['id']}",
            f"/runs/{run['id']}",
            f"/runs/{run['id']}/events",
            f"/workflows/{workflow_id}",
            f"/workflows/{workflow_id}/guide.md",
            f"/artifacts/{shot}",
        ):
            response = await b.client.get(path)
            assert response.status_code == 404, (path, response.status_code)
        for path in (f"/runs/{run['id']}/cancel", f"/workflows/{workflow_id}/reverify"):
            assert (await b.client.post(path)).status_code == 404, path
        assert (await b.client.get("/workflows")).json()["items"] == []
        assert (await b.client.get("/runs")).json()["items"] == []
        mine = Task.model_validate(
            (await b.client.post("/tasks", json={"prompt": "Mine", "target_url": site})).json()
        )
        async with sessions() as s:
            row = await s.get(TaskRow, mine.id)
            assert row is not None and row.user_id == bob.id


async def test_a_session_of_a_deleted_user_signs_nobody_in(sessions: Sessions, tmp_path: Path) -> None:
    user = await make_user(sessions)
    async with Api(services(sessions, tmp_path), user) as api:
        async with sessions.begin() as s:
            await s.delete(await s.get(UserRow, user.id))
        assert (await api.client.get("/auth/me")).status_code == 401

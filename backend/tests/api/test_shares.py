"""Read-only share links (#96), end to end: a real run makes a workflow, its owner shares it, and a client
without any session opens the tutorial and its files."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, update

from app.api import shares
from app.api.accounts import token_hash
from app.contracts_gen.share_schema import ShareLinkCreated, ShareLinkList
from app.contracts_gen.workflow_schema import Workflow
from app.db import TutorialShareRow
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio

GONE = {"error": {"code": "not_found", "message": "This link doesn't exist or no longer works"}}


@pytest.fixture(autouse=True)
def fresh_rate_limit() -> None:
    shares._hits.clear()


async def verified_workflow(api: Api, site: str) -> UUID:
    task = await api.planned_task(site)
    plan = (await api.client.get(f"/plans/{task.plan_id}")).json()
    run = (await api.client.post(f"/plans/{plan['id']}/approve", json={"revision": plan["revision"]})).json()
    await api.svc.executor.wait(UUID(run["id"]))
    return UUID((await api.client.get("/workflows")).json()["items"][0]["id"])


def public(api: Api) -> httpx.AsyncClient:
    """No cookie, no CSRF header: anyone who has the link."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test")


def token_of(created: ShareLinkCreated) -> str:
    return created.url.rsplit("/share/", 1)[1]


async def share(api: Api, workflow_id: UUID) -> ShareLinkCreated:
    response = await api.client.post(f"/workflows/{workflow_id}/shares")
    assert response.status_code == 201, response.text
    return ShareLinkCreated.model_validate(response.json())


async def test_a_shared_tutorial_opens_without_a_session_and_hides_private_ids(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        created = await share(api, workflow_id)
        token = token_of(created)
        assert created.url.startswith("http://localhost:3000/share/") and len(token) >= 43
        assert created.link.revoked_at is None and created.link.expires_at is None

        async with public(api) as c:
            response = await c.get(f"/api/v1/shared/{token}")
            assert response.status_code == 200, response.text
            assert response.headers["referrer-policy"] == "no-referrer"
            assert "noindex" in response.headers["x-robots-tag"]
            assert "no-store" in response.headers["cache-control"]
            shared = Workflow.model_validate(response.json())
            assert (
                shared.id == workflow_id
                and shared.task_id is None
                and shared.run_id is None
                and shared.task is None
            )
            prefix = f"/api/v1/shared/{token}/artifacts/runs/"
            assert shared.recording_path is not None and shared.recording_path.startswith(prefix)
            shot = shared.steps[0].screenshot_path
            assert shot is not None and shot.startswith(prefix)

            image = await c.get(shot)
            assert image.status_code == 200 and image.headers["content-type"] == "image/png"
            recording = await c.get(shared.recording_path)
            assert recording.status_code == 200 and recording.json()

            # The owner's private run, plan and task stay private.
            mine: dict[str, Any] = (await api.client.get(f"/workflows/{workflow_id}")).json()
            for path in (f"/api/v1/runs/{mine['run_id']}", f"/api/v1/workflows/{workflow_id}"):
                assert (await c.get(path)).status_code == 401


async def test_revoking_a_link_stops_it_at_once(sessions: Sessions, site: str, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        keep, revoke = await share(api, workflow_id), await share(api, workflow_id)
        shot = (await api.client.get(f"/workflows/{workflow_id}")).json()["steps"][0]["screenshot_path"]

        revoked = await api.client.delete(f"/workflows/{workflow_id}/shares/{revoke.link.id}")
        assert revoked.status_code == 200 and revoked.json()["revoked_at"]

        async with public(api) as c:
            gone = await c.get(f"/api/v1/shared/{token_of(revoke)}")
            assert gone.status_code == 404 and gone.json() == GONE
            assert (await c.get(f"/api/v1/shared/{token_of(revoke)}/artifacts/{shot}")).status_code == 404
            assert (
                await c.get(f"/api/v1/shared/{token_of(keep)}")
            ).status_code == 200  # the other link still works
        links = ShareLinkList.model_validate(
            (await api.client.get(f"/workflows/{workflow_id}/shares")).json()
        )
        assert {link.id: link.revoked_at is not None for link in links.items} == {
            keep.link.id: False,
            revoke.link.id: True,
        }
        assert "token" not in str(links.model_dump()) and token_of(keep) not in str(links.model_dump())


async def test_unknown_and_expired_links_get_the_same_404(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        created = await share(api, workflow_id)
        async with sessions.begin() as s:
            await s.execute(
                update(TutorialShareRow).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
        async with public(api) as c:
            expired = await c.get(f"/api/v1/shared/{token_of(created)}")
            unknown = await c.get(f"/api/v1/shared/{uuid4().hex}")
    assert expired.status_code == unknown.status_code == 404
    assert expired.json() == unknown.json() == GONE


async def test_only_the_shared_workflows_own_files_are_served(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        first = await verified_workflow(api, site)
        second = await verified_workflow(api, site)
        other_shot = (await api.client.get(f"/workflows/{second}")).json()["steps"][0]["screenshot_path"]
        token = token_of(await share(api, first))

        async with public(api) as c:
            for key in (other_shot, "../secret.json", "runs/../../secret.json", "runs/x/1-after.png"):
                response = await c.get(f"/api/v1/shared/{token}/artifacts/{key}")
                assert response.status_code == 404, key


async def test_only_the_owner_manages_links(sessions: Sessions, site: str, tmp_path: Path) -> None:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN))
    alice, bob = await make_user(sessions), await make_user(sessions)
    async with Api(svc, alice) as a:
        workflow_id = await verified_workflow(a, site)
        link = (await share(a, workflow_id)).link
    async with Api(svc, bob) as b:
        assert (await b.client.post(f"/workflows/{workflow_id}/shares")).status_code == 404
        assert (await b.client.get(f"/workflows/{workflow_id}/shares")).status_code == 404
        assert (await b.client.delete(f"/workflows/{workflow_id}/shares/{link.id}")).status_code == 404
    async with sessions() as s:
        row = await s.get(TutorialShareRow, link.id)
        assert row is not None and row.revoked_at is None


async def test_the_database_keeps_only_the_tokens_hash(sessions: Sessions, site: str, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        token = token_of(await share(api, await verified_workflow(api, site)))
    async with sessions() as s:
        stored = (await s.scalars(select(TutorialShareRow.token_hash))).all()
    assert stored == [token_hash(token)] and token not in stored


async def test_public_reads_are_rate_limited_per_ip(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api, public(api) as c:
        codes = [
            (await c.get(f"/api/v1/shared/{uuid4().hex}")).status_code for _ in range(shares.PER_MINUTE + 1)
        ]
    assert set(codes[:-1]) == {404} and codes[-1] == 429

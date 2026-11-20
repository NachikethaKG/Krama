"""Per-user site sessions (#404, ADR 0007): GET /sites/profiles, POST /sites/{site}/sign-in,
DELETE /sites/{site}/profile.

Signing in is a run of kind `sign_in`: Krama opens the site's sign-in page and pauses; the user takes over
(ADR 0008), signs in by hand and hands back; Krama stores the session encrypted for this user and site. The
session itself never leaves the server.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from app.api.auth import CurrentUser
from app.api.convert import run_out
from app.api.errors import ApiException
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.run_schema import Run
from app.contracts_gen.site_schema import SiteProfile, SiteProfileList
from app.db import PlanRow, RunRow, TaskRow

router = APIRouter(tags=["sites"])
_404: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse, "description": "No such site"}}


@router.get("/sites/profiles")
async def get_profiles(user: CurrentUser, services: ServicesDep) -> SiteProfileList:
    """The sites the user signed Krama in to, and as whom. Never the sessions."""
    rows = await services.profiles.list(user.id) if services.profiles is not None else []
    now = datetime.now(UTC)
    return SiteProfileList(
        items=[
            SiteProfile(site=r.site, account=r.account, captured_at=r.captured_at, expires_at=r.expires_at)
            for r in rows
            if r.expires_at is None or r.expires_at > now
        ]
    )


@router.post("/sites/{site}/sign-in", status_code=202, responses=_404)
async def sign_in(site: str, user: CurrentUser, services: ServicesDep) -> Run:
    """Start a sign-in run: take it over from the live view, sign in by hand, hand it back."""
    url = services.sites.get(site)
    login_path = services.target(url).login_path if url is not None else None
    if url is None or login_path is None:
        raise ApiException(404, "not_found", f"Krama can't sign in to {site!r}")
    # One step, the one it pauses at: open the sign-in page (run.started needs total_steps >= 1).
    step = {
        "seq": 1, "action": {"type": "navigate", "value": login_path}, "target": {},
        "instruction_text": f"Sign in to {site}.", "expected_state": {}, "risk": "low",
    }  # fmt: skip
    async with services.sessions.begin() as s:
        task = TaskRow(user_id=user.id, prompt=f"Sign in to {site}", target_url=url, status="planned")
        s.add(task)
        await s.flush()
        plan = PlanRow(
            task_id=task.id,
            status="approved",
            risk="low",
            expected_result=f"Signed in to {site}",
            steps=[step],
            approved_at=datetime.now(UTC),
        )
        s.add(plan)
        await s.flush()
        run = RunRow(plan_id=plan.id, plan_revision=1, status="queued", kind="sign_in")
        s.add(run)
        await s.flush()
        run_id: UUID = run.id
        out = run_out(run, None)
    await services.executor.submit(run_id)
    return out


@router.delete("/sites/{site}/profile", status_code=204)
async def sign_out(site: str, user: CurrentUser, services: ServicesDep) -> Response:
    """Forget the user's session on that site (Krama is signed out of their account there)."""
    if services.profiles is not None:
        await services.profiles.delete(user.id, site)
    return Response(status_code=204)

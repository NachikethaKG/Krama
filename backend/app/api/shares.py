"""Read-only share links to a tutorial (#96).

Contract: docs/api-contract.md. Design: docs/research/phase-3-vishwas-share-tokens.md.

Owner side (signed in): POST/GET /workflows/{id}/shares, DELETE /workflows/{id}/shares/{share_id}.
Public side (no session): GET /shared/{token} and the workflow's own files under /shared/{token}/artifacts/.

The link holds a 256-bit random token; only its SHA-256 is stored, so the full link is shown once. Unknown,
revoked and expired tokens all get the same 404. The public workflow carries no task, run or owner ids, and
its files are served only if the workflow itself references them.
"""

import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, Response
from sqlalchemy import select

from app.api.accounts import token_hash
from app.api.auth import CurrentUser
from app.api.convert import workflow_out
from app.api.errors import ApiException
from app.api.owner import owned_workflow
from app.api.services import ServicesDep
from app.config import get_settings
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.share_schema import ShareLink, ShareLinkCreated, ShareLinkList
from app.contracts_gen.workflow_schema import Workflow
from app.db import TutorialShareRow, WorkflowRow
from app.ports import ArtifactNotFoundError, ArtifactStore, InvalidArtifactKeyError
from app.storage import get_artifact_store

type Responses = dict[int | str, dict[str, Any]]

router = APIRouter(tags=["shares"])
_404: Responses = {404: {"model": ErrorResponse, "description": "Unknown, revoked or expired link"}}
PUBLIC_HEADERS = {
    "Referrer-Policy": "no-referrer",  # the token must not leak to other sites
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "private, no-store",
}
PER_MINUTE = 120
_hits: defaultdict[str, deque[float]] = defaultdict(deque)
"""Public share requests per client IP in the last minute (cost guard; 256-bit tokens can't be guessed)."""


def share_out(row: TutorialShareRow) -> ShareLink:
    return ShareLink(
        id=row.id,
        workflow_id=row.workflow_id,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        last_used_at=row.last_used_at,
    )


@router.post("/workflows/{workflow_id}/shares", status_code=201, responses=_404)
async def create_share(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> ShareLinkCreated:
    """A new read-only link. `url` holds the secret token: it is returned only here."""
    token = secrets.token_urlsafe(32)
    async with services.sessions.begin() as s:
        await owned_workflow(s, workflow_id, user)
        row = TutorialShareRow(workflow_id=workflow_id, created_by=user.id, token_hash=token_hash(token))
        s.add(row)
        await s.flush()
        await s.refresh(row)
        link = share_out(row)
    base = get_settings().frontend_url.rstrip("/")
    return ShareLinkCreated(link=link, url=f"{base}/share/{token}")


@router.get("/workflows/{workflow_id}/shares", responses=_404)
async def list_shares(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> ShareLinkList:
    async with services.sessions() as s:
        await owned_workflow(s, workflow_id, user)
        rows = await s.scalars(
            select(TutorialShareRow)
            .where(TutorialShareRow.workflow_id == workflow_id)
            .order_by(TutorialShareRow.created_at.desc())
        )
        return ShareLinkList(items=[share_out(r) for r in rows])


@router.delete("/workflows/{workflow_id}/shares/{share_id}", responses=_404)
async def revoke_share(
    workflow_id: UUID, share_id: UUID, user: CurrentUser, services: ServicesDep
) -> ShareLink:
    """Revokes the link at once. It is kept with revoked_at set, so the owner still sees it; revoking twice is
    fine."""
    async with services.sessions.begin() as s:
        await owned_workflow(s, workflow_id, user)
        row = await s.get(TutorialShareRow, share_id)
        if row is None or row.workflow_id != workflow_id:
            raise ApiException(404, "not_found", "Share link not found")
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
        await s.flush()
        return share_out(row)


async def shared_workflow(token: str, request: Request, services: ServicesDep) -> WorkflowRow:
    """The workflow behind a live token, else 404 (the same answer for unknown, revoked and expired)."""
    _limit(request.client.host if request.client else "unknown")
    now = datetime.now(UTC)
    async with services.sessions.begin() as s:
        share = await s.scalar(
            select(TutorialShareRow).where(TutorialShareRow.token_hash == token_hash(token))
        )
        if (
            share is None
            or share.revoked_at is not None
            or (share.expires_at is not None and share.expires_at <= now)
        ):
            raise ApiException(404, "not_found", "This link doesn't exist or no longer works")
        share.last_used_at = now
        workflow = await s.get(WorkflowRow, share.workflow_id)
        if workflow is None:
            raise ApiException(404, "not_found", "This link doesn't exist or no longer works")
        return workflow


SharedWorkflow = Annotated[WorkflowRow, Depends(shared_workflow)]


@router.get("/shared/{token}", responses=_404)
async def get_shared(token: str, workflow: SharedWorkflow, response: Response) -> Workflow:
    """The tutorial's workflow, read-only: no task, run or owner ids, files under /shared/{token}/."""
    response.headers.update(PUBLIC_HEADERS)
    public = workflow_out(workflow, None).model_copy(update={"task_id": None, "run_id": None, "task": None})
    data = public.model_dump(mode="json")
    prefix = f"/api/v1/shared/{token}/artifacts/"
    if data.get("recording_path"):
        data["recording_path"] = prefix + data["recording_path"]
    for step in data["steps"]:
        _point_files(step, prefix)
    return Workflow.model_validate(data)


@router.get(
    "/shared/{token}/artifacts/{key:path}",
    response_class=Response,
    responses={
        **_404,
        200: {"content": {"image/png": {}, "application/json": {}}, "description": "The file"},
    },
)
async def get_shared_artifact(
    workflow: SharedWorkflow,
    key: Annotated[str, Path(description="An artifact key the shared workflow references")],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> Response:
    if key not in _referenced(workflow):
        raise ApiException(404, "not_found", "Artifact not found")
    try:
        artifact = await store.get(key)
    except (ArtifactNotFoundError, InvalidArtifactKeyError):
        raise ApiException(404, "not_found", "Artifact not found") from None
    headers = {
        **PUBLIC_HEADERS,
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    return Response(artifact.data, media_type=artifact.ref.content_type, headers=headers)


def _referenced(workflow: WorkflowRow) -> set[str]:
    """Every file key the workflow points at: its recording and the steps' screenshots."""
    keys: set[str] = {workflow.recording_path} if workflow.recording_path else set()
    for step in workflow.steps:
        keys |= {
            k for k in _screenshot_keys(step.screenshot_path, step.before_state, step.observed_state) if k
        }
    return keys


def _screenshot_keys(*values: Any) -> list[str]:
    found: list[str] = []
    for value in values:
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            found += _screenshot_keys(
                *(v for k, v in value.items() if k == "screenshot_path" or isinstance(v, dict))
            )
    return found


def _point_files(node: Any, prefix: str) -> None:
    """Rewrite every `screenshot_path` key in a step (and its states) to the shared file URL."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "screenshot_path" and isinstance(v, str) and v:
                node[k] = prefix + v
            else:
                _point_files(v, prefix)


def _limit(ip: str) -> None:
    now = time.monotonic()
    recent = _hits[ip]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if len(recent) >= PER_MINUTE:
        raise ApiException(429, "rate_limited", "Too many requests")
    recent.append(now)

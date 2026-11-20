"""GET /workflows/{id} (the Verified Workflow, the main output), its text guide and versions, and
GET /workflows (docs/api-contract.md)."""

from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select

from app.api.auth import CurrentUser
from app.api.convert import (
    decode_cursor,
    encode_cursor,
    run_out,
    task_out,
    version_out,
    workflow_out,
    workflow_summary,
)
from app.api.errors import ApiException
from app.api.guide import guide_markdown
from app.api.owner import owned_workflow
from app.api.services import Services, ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.run_schema import Run
from app.contracts_gen.task_schema import Task
from app.contracts_gen.workflow_schema import (
    RunWorkflowRequest,
    Workflow,
    WorkflowInputList,
    WorkflowPage,
    WorkflowStatus,
    WorkflowVersionList,
)
from app.db import RunRow, TaskRow, UserRow, WorkflowRow
from app.db.repositories import list_versions, list_workflows
from app.db.search import MAX_QUERY, last_validated, search_workflows
from app.runs.do_it import create_do_it_run, workflow_inputs
from app.runs.inputs import DoItRefusedError, InputUnsafeError
from app.runs.reverify import ReverifyRefusedError, create_reverify_run

router = APIRouter(tags=["workflows"])


@router.get("/workflows/{workflow_id}", responses={404: {"model": ErrorResponse, "description": "Not found"}})
async def get_workflow(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> Workflow:
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        task = await s.get(TaskRow, workflow.task_id)
        return workflow_out(workflow, task.prompt if task else None)


@router.get(
    "/workflows/{workflow_id}/guide.md",
    response_class=Response,
    responses={
        200: {"content": {"text/markdown": {}}, "description": "Numbered steps with one screenshot each"},
        404: {"model": ErrorResponse, "description": "Not found"},
    },
)
async def get_workflow_guide(
    workflow_id: UUID, request: Request, user: CurrentUser, services: ServicesDep
) -> Response:
    """The workflow as a plain text guide: the tutorial's step texts, numbered, each with its screenshot."""
    workflow = await get_workflow(workflow_id, user, services)

    def artifact_url(key: str) -> str:
        # Absolute, so the file still shows its images when opened outside the app.
        return str(request.url_for("get_artifact", key=quote(key)))

    return Response(
        guide_markdown(workflow, artifact_url),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="workflow-{workflow_id}.md"'},
    )


@router.get(
    "/workflows/{workflow_id}/versions", responses={404: {"model": ErrorResponse, "description": "Not found"}}
)
async def get_workflow_versions(
    workflow_id: UUID, user: CurrentUser, services: ServicesDep
) -> WorkflowVersionList:
    """Every version of the workflow, newest first, each with its step diff against its parent (Phase 4)."""
    async with services.sessions() as s:
        await owned_workflow(s, workflow_id, user)
        return WorkflowVersionList(items=[version_out(v, n) for v, n in await list_versions(s, workflow_id)])


@router.post(
    "/workflows/{workflow_id}/regenerate",
    status_code=202,
    responses={404: {"model": ErrorResponse, "description": "Not found"}},
)
async def regenerate_workflow(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> Task:
    """Re-plan a workflow that can't heal (#113), from its original prompt and URL. Like POST /tasks: poll the
    task, then review and approve its plan. When that run verifies, its steps become this workflow's next
    version (D3); no new workflow."""
    async with services.sessions.begin() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        original = await s.get(TaskRow, workflow.task_id)
        task = TaskRow(
            user_id=user.id,
            prompt=original.prompt if original else workflow.title,
            target_url=workflow.target_url,
            status="planning",
            regenerates_workflow_id=workflow.id,
        )
        s.add(task)
        await s.flush()
        out = task_out(task, None)
    services.planning.submit(task.id)
    return out


@router.post(
    "/workflows/{workflow_id}/reverify",
    status_code=202,
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {
            "model": ErrorResponse,
            "description": "A step is high risk or typed a secret, or the reset failed",
        },
    },
)
async def reverify_workflow(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> Run:
    """Replay the stored workflow's steps headlessly, without the planner (#77). The run stores no new
    workflow; its events and final status say whether every step still works."""
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        target_url = workflow.target_url
    try:
        run_id = await create_reverify_run(services.sessions, workflow_id, services.target(target_url).reset)
    except ReverifyRefusedError as e:
        details: dict[str, Any] = {"reason": e.reason}
        if e.step_seq is not None:
            details["step_seq"] = e.step_seq
        raise ApiException(409, "conflict", str(e), details) from None
    async with services.sessions() as s:
        run = await s.get(RunRow, run_id)
        assert run is not None
        out = run_out(run, None)
    await services.executor.submit(run_id)
    return out


_DO_IT_REFUSALS = "Not verified, a version waits for review, a step typed a secret, or the version is stale"


def _refused(e: DoItRefusedError) -> ApiException:
    details: dict[str, Any] = {"reason": e.reason}
    if e.step_seq is not None:
        details["step_seq"] = e.step_seq
    return ApiException(409, "conflict", str(e), details)


@router.get(
    "/workflows/{workflow_id}/inputs",
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": _DO_IT_REFUSALS},
    },
)
async def get_workflow_inputs(
    workflow_id: UUID, user: CurrentUser, services: ServicesDep
) -> WorkflowInputList:
    """The values the owner chooses before "Do it for me" runs the current version (#129), and the site
    account the run acts in: in v1 the account Krama is signed in to there, not the user's own (P11)."""
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        account, needs = await _account(services, user, workflow.target_url)
        try:
            return await workflow_inputs(s, workflow, account, needs)
        except DoItRefusedError as e:
            raise _refused(e) from None


async def _account(services: Services, user: UserRow, target_url: str) -> tuple[str | None, str | None]:
    """The account a do-it run acts in, and the site to sign in to first (ADR 0007). Sites without sign-in
    (local test pages) need no session."""
    target = services.target(target_url)
    if target.login_path is None or services.profiles is None or target.site is None:
        return target.signed_in_as, None
    profile = await services.profiles.load(user.id, target.site)
    return (profile.account, None) if profile is not None else (None, target.site)


@router.post(
    "/workflows/{workflow_id}/run",
    status_code=202,
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": _DO_IT_REFUSALS},
        422: {
            "model": ErrorResponse,
            "description": "A value is missing, unknown or can't be used (input_unsafe)",
        },
    },
)
async def run_workflow(
    workflow_id: UUID, body: RunWorkflowRequest, user: CurrentUser, services: ServicesDep
) -> Run:
    """ "Do it for me" (#129): run the stored steps for the owner with their values. Starting it approves the
    steps; it never resets the site, risky steps pause for confirmation, and no workflow is stored."""
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        target_url = workflow.target_url
    account, needs = await _account(services, user, target_url)
    if needs is not None:
        message = f"Sign in to {needs} first: Krama acts in your own account"
        raise ApiException(409, "conflict", message, {"reason": "site_sign_in_needed", "site": needs})
    swap = (services.target(target_url).signed_in_as, account) if account is not None else None
    try:
        run_id = await create_do_it_run(
            services.sessions, workflow_id, body.revision, body.inputs, account=swap
        )
    except DoItRefusedError as e:
        raise _refused(e) from None
    except InputUnsafeError as e:
        details = {"reason": "input_unsafe", "key": e.key}
        raise ApiException(422, "validation_error", str(e), details) from None
    async with services.sessions() as s:
        run = await s.get(RunRow, run_id)
        assert run is not None
        out = run_out(run, None)
    await services.executor.submit(run_id)
    return out


@router.get("/workflows")
async def get_workflows(
    user: CurrentUser,
    services: ServicesDep,
    target_app: str | None = None,
    status: WorkflowStatus | None = None,
    q: Annotated[str | None, Query(max_length=MAX_QUERY)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> WorkflowPage:
    """Stored workflows, newest first, optionally for one app (e.g. gitea) or status. With `q`: searched and
    ranked (#135), paged by `offset`; `next_cursor` is then the next offset."""
    if q is not None and q.strip():
        return await _search(user, services, q, status, min(limit, 50), offset)
    async with services.sessions() as s:
        rows = await list_workflows(
            s,
            user_id=user.id,
            limit=limit,
            target_app=target_app,
            status=status,
            before=decode_cursor(cursor),
        )
        checked = await last_validated(s, [r.id for r in rows])
        items = [workflow_summary(r, last_validated_at=checked.get(r.id)) for r in rows]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return WorkflowPage(items=items, next_cursor=next_cursor)


async def _search(
    user: UserRow, services: Services, q: str, status: str | None, limit: int, offset: int
) -> WorkflowPage:
    async with services.sessions() as s:
        hits = await search_workflows(s, user_id=user.id, query=q, status=status, limit=limit, offset=offset)
        rows = {
            r.id: r
            for r in await s.scalars(
                select(WorkflowRow).where(WorkflowRow.id.in_([h.workflow_id for h in hits]))
            )
        }
        items = [workflow_summary(rows[h.workflow_id], hit=h) for h in hits if h.workflow_id in rows]
    return WorkflowPage(items=items, next_cursor=str(offset + limit) if len(hits) == limit else None)

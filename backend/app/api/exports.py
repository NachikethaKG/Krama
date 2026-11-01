"""MP4 export (#124, docs/api-contract.md): request an export, poll it, download the video and its captions.

Rendering happens in the export job behind the `ExportQueue` port (Nachiketha, #126). Until that job exists,
the API uses the mock queue from `app.ports.fakes`, which "renders" at once with a fixture MP4 (decision D14),
so the export dialog (#127) can be built against the real API.
"""

import re
import unicodedata
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.errors import ApiException
from app.api.owner import owned_workflow
from app.api.services import ServicesDep
from app.config import get_settings
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.export_schema import CreateExportRequest, Export
from app.db import ExportRow, WorkflowRow, WorkflowVersionRow
from app.ports import ArtifactFiles, ArtifactNotFoundError, ExportQueue
from app.ports.fakes import FakeExportQueue
from app.runs.exports import DbExportStore, export_view, find_reusable
from app.storage import get_artifact_files

router = APIRouter(tags=["exports"])

_404: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse, "description": "Not found"}}
# The files are only ever data: no type guessing, nothing runs inside them.
_FILE_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"}


def get_export_queue(
    services: ServicesDep, files: Annotated[ArtifactFiles, Depends(get_artifact_files)]
) -> ExportQueue:
    """The mock queue until the arq export job exists (#126). TODO(vishwas): switch to the real queue then."""
    return FakeExportQueue(DbExportStore(services.sessions), files)


@router.post(
    "/workflows/{workflow_id}/exports",
    status_code=202,
    responses={
        200: {
            "model": Export,
            "description": "The same version, preset and voice is already exported or on its way",
        },
        **_404,
        409: {
            "model": ErrorResponse,
            "description": "The workflow isn't verified (outdated or a heal is pending)",
        },
    },
)
async def create_export(
    workflow_id: UUID,
    body: CreateExportRequest,
    response: Response,
    user: CurrentUser,
    services: ServicesDep,
    queue: Annotated[ExportQueue, Depends(get_export_queue)],
) -> Export:
    """Export the workflow's current version as an MP4 (D13-D17): re-use a queued, rendering or ready export
    of the same version, preset and voice; otherwise queue a new one."""
    voice = get_settings().tts_voice
    async with services.sessions.begin() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        # Lock the workflow row: two clicks at once must not queue two renders.
        await s.refresh(workflow, with_for_update=True)
        if workflow.status != "verified" or workflow.current_version_id is None:
            raise ApiException(
                409,
                "conflict",
                "Only a verified workflow can be exported. Check or fix it first.",
                {"reason": "workflow_not_verified", "status": workflow.status},
            )
        existing = await find_reusable(
            s,
            workflow_id=workflow.id,
            version_id=workflow.current_version_id,
            preset=body.preset,
            voice=voice,
        )
        if existing is not None:
            response.status_code = 200
            return await export_view(s, existing)
        row = ExportRow(
            workflow_id=workflow.id,
            version_id=workflow.current_version_id,
            user_id=user.id,
            preset=body.preset,
            voice=voice,
            status="queued",
            progress=0,
        )
        s.add(row)
        await s.flush()
        await s.refresh(row)
        created = await export_view(s, row)
    try:
        await queue.enqueue(row.id)
    except Exception as e:
        await DbExportStore(services.sessions).mark_failed(
            row.id, "internal", "The export couldn't be queued."
        )
        raise ApiException(503, "internal", "The export couldn't be queued. Try again.") from e
    return created


@router.get("/exports/{export_id}", responses=_404)
async def get_export(export_id: UUID, user: CurrentUser, services: ServicesDep) -> Export:
    async with services.sessions() as s:
        return await export_view(s, await _owned_export(s, export_id, user.id))


@router.get(
    "/exports/{export_id}/download",
    response_class=FileResponse,
    responses={
        200: {"content": {"video/mp4": {}}, "description": "The MP4 (supports Range requests)"},
        **_404,
        409: {"model": ErrorResponse, "description": "The export isn't ready"},
    },
)
async def download_export(
    export_id: UUID,
    user: CurrentUser,
    services: ServicesDep,
    files: Annotated[ArtifactFiles, Depends(get_artifact_files)],
) -> FileResponse:
    async with services.sessions() as s:
        row = await _owned_export(s, export_id, user.id)
        workflow = await s.get(WorkflowRow, row.workflow_id)
        version = await s.get(WorkflowVersionRow, row.version_id)
    if row.status != "ready" or row.video_key is None:
        raise ApiException(
            409, "conflict", f"The export is {row.status}, not ready.", {"reason": "export_not_ready"}
        )
    path = await _local_file(files, row.video_key)
    name = f"{_slug(workflow.title if workflow else 'tutorial')}-v{version.revision if version else 1}"
    return FileResponse(
        path, media_type="video/mp4", filename=f"{name}-{row.preset}.mp4", headers=_FILE_HEADERS
    )


@router.get(
    "/exports/{export_id}/captions.vtt",
    response_class=FileResponse,
    responses={200: {"content": {"text/vtt": {}}, "description": "WebVTT captions"}, **_404},
)
async def export_captions(
    export_id: UUID,
    user: CurrentUser,
    services: ServicesDep,
    files: Annotated[ArtifactFiles, Depends(get_artifact_files)],
) -> FileResponse:
    async with services.sessions() as s:
        row = await _owned_export(s, export_id, user.id)
    if row.status != "ready" or row.captions_key is None:
        raise ApiException(404, "not_found", "This export has no captions")
    path = await _local_file(files, row.captions_key)
    return FileResponse(path, media_type="text/vtt; charset=utf-8", headers=_FILE_HEADERS)


async def _owned_export(s: AsyncSession, export_id: UUID, user_id: UUID) -> ExportRow:
    """Someone else's export answers like a missing one (404), so ids can't be probed."""
    row = await s.get(ExportRow, export_id)
    workflow = await s.get(WorkflowRow, row.workflow_id) if row else None
    if row is None or workflow is None or workflow.user_id != user_id:
        raise ApiException(404, "not_found", "Export not found")
    return row


async def _local_file(files: ArtifactFiles, key: str) -> Path:
    try:
        return await files.local_path(key)
    except ArtifactNotFoundError:
        # The row says ready but the file is gone (deleted by hand, or a different ARTIFACTS_DIR).
        raise ApiException(404, "not_found", "The exported file is missing. Export again.") from None


def _slug(title: str) -> str:
    """An ASCII file name from the workflow title ("Create a repository" -> "create-a-repository")."""
    ascii_ = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:60] or "tutorial"

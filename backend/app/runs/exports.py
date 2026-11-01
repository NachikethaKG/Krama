"""Exports on the `exports` table (#124): the `ExportStore` port for the export job, and create-or-reuse for
`POST /workflows/{id}/exports` (decisions D13-D16 in docs/research/phase-5-decisions-alignment.md).

Status changes are single conditional UPDATEs (`... WHERE status IN (...)`), like runs, so two writers can't
move an export backwards or finish it twice.
"""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.convert import export_out, workflow_version_out
from app.contracts_gen.export_schema import Export, ExportErrorCode, ExportPreset
from app.db import ExportRow, TaskRow, WorkflowRow, WorkflowStepRow, WorkflowVersionRow
from app.ports.exports import ExportJobInput, ExportNotFoundError, ExportStateError, ExportStore
from app.ports.models import ArtifactRef

REUSABLE = ("queued", "rendering", "ready")
"""An export in one of these is returned again for the same version, preset and voice (D16)."""
MAX_MESSAGE = 500


class DbExportStore:
    """`ExportStore` (app/ports/exports.py) for the export job."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def load(self, export_id: UUID) -> ExportJobInput:
        async with self.sessions() as s:
            row = await _get(s, export_id)
            workflow = await s.get(WorkflowRow, row.workflow_id)
            version = await s.get(WorkflowVersionRow, row.version_id)
            if workflow is None or version is None:  # both cascade-delete the export: can't happen
                raise ExportNotFoundError(str(export_id))
            steps = (
                await s.scalars(
                    select(WorkflowStepRow)
                    .where(WorkflowStepRow.version_id == version.id)
                    .order_by(WorkflowStepRow.seq)
                )
            ).all()
            task = await s.get(TaskRow, workflow.task_id)
            return ExportJobInput(
                export=export_out(row, title=workflow.title, revision=version.revision),
                workflow=workflow_version_out(workflow, version, steps, task.prompt if task else None),
            )

    async def mark_rendering(self, export_id: UUID, progress: int) -> None:
        step = min(max(progress, 0), 99)
        await self._change(
            export_id,
            ("queued", "rendering"),
            status="rendering",
            progress=func.greatest(ExportRow.progress, step),
            started_at=func.coalesce(ExportRow.started_at, func.now()),
        )

    async def mark_ready(
        self, export_id: UUID, *, video: ArtifactRef, captions: ArtifactRef | None, duration_ms: int
    ) -> None:
        await self._change(
            export_id,
            ("rendering",),
            status="ready",
            progress=100,
            video_key=video.key,
            captions_key=captions.key if captions else None,
            size_bytes=video.size_bytes,
            duration_ms=duration_ms,
            finished_at=func.now(),
        )

    async def mark_failed(self, export_id: UUID, code: ExportErrorCode, message: str) -> None:
        await self._change(
            export_id,
            ("queued", "rendering"),
            status="failed",
            error_code=code,
            error_message=message[:MAX_MESSAGE],
            finished_at=func.now(),
        )

    async def _change(self, export_id: UUID, from_: tuple[str, ...], **values: object) -> None:
        async with self.sessions.begin() as s:
            changed = await s.scalar(
                update(ExportRow)
                .where(ExportRow.id == export_id, ExportRow.status.in_(from_))
                .values(**values, updated_at=func.now())
                .returning(ExportRow.id)
            )
            if changed is None:
                row = await _get(s, export_id)
                raise ExportStateError(f"export {export_id} is {row.status}, expected one of {from_}")


async def find_reusable(
    s: AsyncSession, *, workflow_id: UUID, version_id: UUID, preset: ExportPreset, voice: str
) -> ExportRow | None:
    """The newest queued, rendering or ready export of this version, preset and voice (D16)."""
    row: ExportRow | None = await s.scalar(
        select(ExportRow)
        .where(
            ExportRow.workflow_id == workflow_id,
            ExportRow.version_id == version_id,
            ExportRow.preset == preset,
            ExportRow.voice == voice,
            ExportRow.status.in_(REUSABLE),
        )
        .order_by(ExportRow.created_at.desc())
        .limit(1)
    )
    return row


async def export_view(s: AsyncSession, row: ExportRow) -> Export:
    """The contract `Export`, with the workflow's title and the exported version's number."""
    workflow = await s.get(WorkflowRow, row.workflow_id)
    version = await s.get(WorkflowVersionRow, row.version_id)
    return export_out(
        row, title=workflow.title if workflow else None, revision=version.revision if version else 1
    )


async def _get(s: AsyncSession, export_id: UUID) -> ExportRow:
    row = await s.get(ExportRow, export_id, populate_existing=True)
    if row is None:
        raise ExportNotFoundError(str(export_id))
    return row


def _conforms(store: DbExportStore) -> ExportStore:
    return store  # strict mypy fails here if DbExportStore drifts from the port

"""Ports between the export API (Vishwas, #124) and the export job (Nachiketha, #126).

Flow (decision D14 in docs/research/phase-5-decisions-alignment.md):
1. `POST /workflows/{id}/exports` writes an `exports` row (`queued`) and calls
   `ExportQueue.enqueue(export_id)`.
2. The job (arq queue `krama:exports`, one at a time, no retry) calls `ExportStore.load(export_id)`. If the
   export is already `rendering`, a worker died under it: the job calls `mark_failed(..., "interrupted", ...)`
   and stops. Otherwise it calls `mark_rendering(export_id, 0)`, narrates (`Narrator`), renders, and reports
   progress.
3. It stores the MP4 at `exports/<export_id>.mp4` (and captions at `exports/<export_id>.vtt`) through
   `ArtifactFiles.put_file` and calls `mark_ready`, or `mark_failed`.
4. The UI polls `GET /exports/{id}` every 2 s.
"""

from typing import Protocol
from uuid import UUID

from app.contracts_gen.export_schema import Export, ExportErrorCode
from app.contracts_gen.workflow_schema import Workflow
from app.ports.models import ArtifactRef, _Model

__all__ = [
    "ExportJobInput",
    "ExportNotFoundError",
    "ExportQueue",
    "ExportStateError",
    "ExportStore",
]


class ExportNotFoundError(LookupError):
    """No export with this id."""


class ExportStateError(RuntimeError):
    """The export isn't in a status that allows this change (e.g. `mark_ready` on a `failed` export)."""


class ExportJobInput(_Model):
    """Everything the export job needs to render."""

    export: Export
    workflow: Workflow
    """The exported version, same shape as `GET /workflows/{id}` (steps, viewport, `recording_path`)."""


class ExportQueue(Protocol):
    """Hands an export to the export job. Implemented by `app.export` (arq, #126)."""

    async def enqueue(self, export_id: UUID) -> None:
        """Queue the export. Returns at once; the job runs later in the worker."""
        ...


class ExportStore(Protocol):
    """The export job's view of the `exports` table. Implemented by `app.db`/`app.runs` (Vishwas, #124).

    Status moves only forward: queued -> rendering -> ready | failed (expired is set by cleanup, #125).
    Every method raises ExportNotFoundError for an unknown id.
    """

    async def load(self, export_id: UUID) -> ExportJobInput:
        """The export and the workflow version it renders."""
        ...

    async def mark_rendering(self, export_id: UUID, progress: int) -> None:
        """queued -> rendering (sets `started_at`), or a progress update (0-99) while rendering.
        Progress never goes down. Raises ExportStateError if the export is ready, failed or expired."""
        ...

    async def mark_ready(
        self, export_id: UUID, *, video: ArtifactRef, captions: ArtifactRef | None, duration_ms: int
    ) -> None:
        """rendering -> ready, progress 100. `video` is the stored MP4, `captions` the stored .vtt.
        Raises ExportStateError unless the export is rendering."""
        ...

    async def mark_failed(self, export_id: UUID, code: ExportErrorCode, message: str) -> None:
        """queued or rendering -> failed. `message` is shown to the user: no secrets, no stack traces.
        Raises ExportStateError if the export is already ready, failed or expired."""
        ...

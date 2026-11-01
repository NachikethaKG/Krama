"""Cleanup of exported videos and narration clips (#125; D18-D19 in phase-5-decisions-alignment.md).

Runs daily in the worker (`just backend worker`) and on demand: `uv run krama exports cleanup [--dry-run]`.

1. A failed export's partial files go at once.
2. Files under `exports/` that no export row knows go after a day (a crash between storing and marking
   ready).
3. Every `ready` export except the newest per (workflow version, preset) expires `retention` after it
   finished.
4. While `exports/` is bigger than `max_bytes`: unprotected exports go oldest-first, then, as a last resort,
   protected ones (superseded versions before current ones).
5. Narration clips older than `retention` whose text is no step of any workflow's current version go.

"Expire" = delete the files, then set the row to `expired` (it stays, so the UI can say "expired, export
again"). A file that can't be deleted right now (Windows: someone is downloading it) is skipped and retried on
the next run.
"""

import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import ExportRow, WorkflowRow, WorkflowStepRow
from app.ports import ArtifactFiles
from app.ports.models import ArtifactInfo

logger = logging.getLogger(__name__)

ORPHAN_GRACE = timedelta(days=1)
IN_PROGRESS = ("queued", "rendering")


@dataclass
class CleanupReport:
    dry_run: bool
    expired: list[UUID] = field(default_factory=list)
    """Exports set to `expired` (their files deleted)."""
    expired_over_cap: list[UUID] = field(default_factory=list)
    """The part of `expired` that went only because of the disk cap."""
    deleted_files: list[str] = field(default_factory=list)
    busy: list[str] = field(default_factory=list)
    """Files that couldn't be deleted now (in use); tried again next time."""
    bytes_freed: int = 0
    bytes_after: int = 0

    def summary(self) -> str:
        verb = "would free" if self.dry_run else "freed"
        return (
            f"{len(self.expired)} export(s) expired ({len(self.expired_over_cap)} over the cap), "
            f"{len(self.deleted_files)} file(s) deleted, {verb} {self.bytes_freed / 1e6:.1f} MB, "
            f"exports now {self.bytes_after / 1e6:.1f} MB"
            + (f", {len(self.busy)} busy file(s) left for next time" if self.busy else "")
        )


async def cleanup(
    sessions: async_sessionmaker[AsyncSession],
    files: ArtifactFiles,
    *,
    now: datetime,
    retention: timedelta,
    max_bytes: int,
    dry_run: bool = False,
) -> CleanupReport:
    report = CleanupReport(dry_run=dry_run)
    on_disk = {i.key: i for i in await files.list("exports/")}
    async with sessions() as s:
        rows = list((await s.scalars(select(ExportRow))).all())
        current_versions = set((await s.scalars(select(WorkflowRow.current_version_id))).all())

    async def drop(key: str) -> bool:
        info = on_disk.get(key)
        if info is None:
            return True
        if not dry_run:
            try:
                await files.delete(key)
            except PermissionError:
                report.busy.append(key)
                return False
        report.deleted_files.append(key)
        report.bytes_freed += info.size_bytes
        del on_disk[key]
        return True

    async def expire(row: ExportRow) -> bool:
        keys = [k for k in (row.video_key, row.captions_key) if k]
        if not all([await drop(k) for k in keys]):
            return False
        if not dry_run:
            async with sessions.begin() as s:
                await s.execute(
                    update(ExportRow)
                    .where(ExportRow.id == row.id, ExportRow.status == "ready")
                    .values(status="expired", video_key=None, captions_key=None)
                )
        report.expired.append(row.id)
        return True

    # 1. partial files of failed exports
    for row in rows:
        if row.status == "failed":
            for key in _keys_of(row):
                await drop(key)

    # 2. files no export row knows
    known = {k for row in rows for k in _keys_of(row)}
    for key, info in list(on_disk.items()):
        if key not in known and now - info.modified_at > ORPHAN_GRACE:
            await drop(key)

    # 3. old, unprotected ready exports
    ready = sorted((r for r in rows if r.status == "ready"), key=_finished)
    protected = _newest_per_version_and_preset(ready)
    for row in ready:
        if row.id not in protected and row.finished_at is not None and now - row.finished_at > retention:
            await expire(row)

    # 4. the disk cap: unprotected oldest-first, then protected (superseded versions first)
    expired = set(report.expired)
    left = [r for r in ready if r.id not in expired]
    order = (
        [r for r in left if r.id not in protected]
        + [r for r in left if r.id in protected and r.version_id not in current_versions]
        + [r for r in left if r.id in protected and r.version_id in current_versions]
    )
    for row in order:
        if _total(on_disk.values()) <= max_bytes:
            break
        if await expire(row):
            report.expired_over_cap.append(row.id)

    # 5. narration clips nobody's current steps say any more
    await _clean_clips(sessions, files, report, now=now, retention=retention, dry_run=dry_run)

    report.bytes_after = _total(on_disk.values())
    logger.info("export cleanup%s: %s", " (dry run)" if dry_run else "", report.summary())
    return report


async def cleanup_with_settings(
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    files: ArtifactFiles,
    *,
    dry_run: bool = False,
) -> CleanupReport:
    """`cleanup` with EXPORTS_RETENTION_DAYS and EXPORTS_MAX_GB (the worker's cron and the CLI)."""
    return await cleanup(
        sessions,
        files,
        now=datetime.now(UTC),
        retention=timedelta(days=settings.exports_retention_days),
        max_bytes=int(settings.exports_max_gb * 1e9),
        dry_run=dry_run,
    )


async def _clean_clips(
    sessions: async_sessionmaker[AsyncSession],
    files: ArtifactFiles,
    report: CleanupReport,
    *,
    now: datetime,
    retention: timedelta,
    dry_run: bool,
) -> None:
    clips: dict[str, list[ArtifactInfo]] = {}
    for info in await files.list("narration/"):
        stem = info.key.rsplit(".", 1)[0]  # narration/<voice>/<sha>
        clips.setdefault(stem, []).append(info)
    if not clips:
        return
    async with sessions() as s:
        texts = (
            await s.scalars(
                select(WorkflowStepRow.instruction_text)
                .join(WorkflowRow, WorkflowRow.current_version_id == WorkflowStepRow.version_id)
                .distinct()
            )
        ).all()
    live = {hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts}
    for stem, parts in clips.items():
        sha = stem.rsplit("/", 1)[-1]
        newest = max(p.modified_at for p in parts)
        if sha in live or now - newest <= retention:
            continue
        for part in parts:
            if not dry_run:
                try:
                    await files.delete(part.key)
                except PermissionError:
                    report.busy.append(part.key)
                    continue
            report.deleted_files.append(part.key)
            report.bytes_freed += part.size_bytes


def _keys_of(row: ExportRow) -> set[str]:
    """The keys the row names, plus where the export job writes them (exports/<id>.mp4 / .vtt)."""
    keys = {f"exports/{row.id}.mp4", f"exports/{row.id}.vtt"}
    keys.update(k for k in (row.video_key, row.captions_key) if k)
    return keys


def _finished(row: ExportRow) -> datetime:
    return row.finished_at or row.created_at


def _newest_per_version_and_preset(ready: Iterable[ExportRow]) -> set[UUID]:
    newest: dict[tuple[UUID, str], ExportRow] = {}
    for row in ready:
        key = (row.version_id, row.preset)
        if key not in newest or _finished(row) >= _finished(newest[key]):
            newest[key] = row
    return {row.id for row in newest.values()}


def _total(infos: Iterable[ArtifactInfo]) -> int:
    return sum(i.size_bytes for i in infos)

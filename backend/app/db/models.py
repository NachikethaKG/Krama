"""The tables (docs/database-schema.md). Status values come from the generated contract types.

Row classes are named `…Row` so they never get confused with the contract models of the same name.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contracts_gen.common_schema import Risk
from app.contracts_gen.export_schema import ExportErrorCode, ExportPreset, ExportStatus
from app.contracts_gen.plan_schema import PlanStatus
from app.contracts_gen.run_schema import RunKind, RunStatus
from app.contracts_gen.task_schema import TaskStatus
from app.contracts_gen.workflow_schema import (
    ValidationStatus,
    WorkflowStatus,
    WorkflowVersionSource,
    WorkflowVersionStatus,
)
from app.db.base import Base, Timestamps, literal_values, status_check

TASK_STATUSES = literal_values(TaskStatus)
PLAN_STATUSES = literal_values(PlanStatus)
RUN_STATUSES = literal_values(RunStatus)
RUN_KINDS = literal_values(RunKind)
WORKFLOW_STATUSES = literal_values(WorkflowStatus)
WORKFLOW_VERSION_SOURCES = literal_values(WorkflowVersionSource)
WORKFLOW_VERSION_STATUSES = literal_values(WorkflowVersionStatus)
VALIDATION_STATUSES = literal_values(ValidationStatus)
RISKS = literal_values(Risk)
EXPORT_STATUSES = literal_values(ExportStatus)
EXPORT_PRESETS = literal_values(ExportPreset)
EXPORT_ERROR_CODES = literal_values(ExportErrorCode)


class UserRow(Timestamps, Base):
    """A seeded account (#94; no public sign-up in the MVP). Only an argon2id hash of the password."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    """Lower-cased."""
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text, default=None)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    """Failed sign-ins in a row; each one past the first few doubles the wait before the next try."""
    last_failed_at: Mapped[datetime | None] = mapped_column(default=None)


class SessionRow(Timestamps, Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 is stored, so a leaked table
    signs nobody in (docs/research/phase-3-vishwas-accounts-and-csrf.md)."""

    __tablename__ = "sessions"
    __table_args__ = (Index(None, "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column()
    """The absolute limit; the idle limit is counted from last_seen_at."""
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class TaskRow(Timestamps, Base):
    __tablename__ = "tasks"
    __table_args__ = (status_check("status", TASK_STATUSES, "status"), Index(None, "user_id"))

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    """The owner. Its plans, runs and their files belong to them too. Null only for rows from before #94."""
    prompt: Mapped[str] = mapped_column(Text)
    target_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    interpretation: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    clarification_question: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    regenerates_workflow_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL", use_alter=True), default=None
    )
    """Set by POST /workflows/{id}/regenerate (#113): this task's verified run becomes that workflow's next
    version instead of a new workflow."""


class PlanRow(Timestamps, Base):
    __tablename__ = "plans"
    __table_args__ = (
        status_check("status", PLAN_STATUSES, "status"),
        status_check("risk", RISKS, "risk"),
        Index(None, "task_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(Text, default="proposed", server_default="proposed")
    risk: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)
    steps: Mapped[list[Any]] = mapped_column()  # an editable document, so jsonb rather than rows
    approved_at: Mapped[datetime | None] = mapped_column(default=None)


class RunRow(Timestamps, Base):
    __tablename__ = "runs"
    __table_args__ = (
        status_check("status", RUN_STATUSES, "status"),
        status_check("kind", RUN_KINDS, "kind"),
        Index(None, "plan_id"),
        Index(None, "status"),
        Index(None, "created_at"),  # run history pages, newest first
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"))
    plan_revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text, default="task", server_default="task")
    """task: a run of a newly approved plan. reverify: a replay of a stored workflow's steps (#77)."""
    source_workflow_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL", use_alter=True), default=None
    )
    """reverify only: the stored workflow this run replays. It stores no new workflow."""
    status: Mapped[str] = mapped_column(Text, default="queued", server_default="queued")
    current_seq: Mapped[int | None] = mapped_column(Integer, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # seq of the last run_events row; bumped in the same UPDATE that writes the event (gapless, race-free)
    last_event_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    browser_session: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)


class RunEventRow(Timestamps, Base):
    """The persisted SSE stream. `data` holds the event's own fields; type, run_id, seq and ts are columns."""

    __tablename__ = "run_events"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column()
    ts: Mapped[datetime] = mapped_column(server_default=func.now())


class WorkflowRow(Timestamps, Base):
    """A stored workflow: its identity (share links, tutorial URLs and reverify point here) plus copies of its
    current version's confidence, recording and viewport, so readers need one row. Its versions are
    `WorkflowVersionRow`s (docs/research/phase-4-decisions-alignment.md D1)."""

    __tablename__ = "workflows"
    __table_args__ = (
        status_check("status", WORKFLOW_STATUSES, "status"),
        Index(None, "target_app", "status"),
        Index(None, "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), unique=True)
    """The run that recorded its first version (one run makes one workflow)."""
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    """The task's owner, copied when the workflow is stored (lists and share links filter on it)."""
    title: Mapped[str] = mapped_column(Text)
    target_app: Mapped[str] = mapped_column(Text)
    target_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    """The current version's number."""
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="SET NULL", use_alter=True), default=None
    )
    """The version shown. Null only between inserting the workflow and its first version."""
    confidence: Mapped[float | None] = mapped_column(REAL, default=None)
    preconditions: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")
    recording_path: Mapped[str | None] = mapped_column(Text, default=None)
    viewport: Mapped[dict[str, Any] | None] = mapped_column(default=None)

    steps: Mapped[list["WorkflowStepRow"]] = relationship(
        primaryjoin="WorkflowRow.current_version_id == foreign(WorkflowStepRow.version_id)",
        order_by="WorkflowStepRow.seq",
        lazy="selectin",
        viewonly=True,
    )
    """The current version's steps. Read-only: steps are written through `WorkflowVersionRow.steps`."""


class WorkflowVersionRow(Timestamps, Base):
    """One version of a workflow, with its own step rows and recording. Immutable once written except for
    `status` (docs/database-schema.md)."""

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "revision"),
        status_check("source", WORKFLOW_VERSION_SOURCES, "source"),
        status_check("status", WORKFLOW_VERSION_STATUSES, "status"),
        # At most one current version per workflow.
        Index(
            "ix_workflow_versions_one_current",
            "workflow_id",
            unique=True,
            postgresql_where=text("status = 'current'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    parent_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="SET NULL"), default=None
    )
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), default=None)
    """The run that recorded this version."""
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    """Who asked for it (regenerate, edit). Null for the first version and for heals."""
    confidence: Mapped[float | None] = mapped_column(REAL, default=None)
    recording_path: Mapped[str | None] = mapped_column(Text, default=None)
    viewport: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    change_summary: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    """A contract `StepDiff` against the parent version; null for the first."""

    steps: Mapped[list["WorkflowStepRow"]] = relationship(
        order_by="WorkflowStepRow.seq", lazy="raise_on_sql", cascade="all, delete-orphan"
    )
    """Not loaded with the version (a list of versions needs only counts): load it explicitly."""


class ValidationRow(Timestamps, Base):
    """One validation of a stored workflow (Phase 4; written by `validation/`, #110)."""

    __tablename__ = "validations"
    __table_args__ = (
        status_check("status", VALIDATION_STATUSES, "status"),
        Index(None, "workflow_id", "ran_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="SET NULL"), default=None
    )
    """The version that was validated."""
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), default=None)
    """The reverify run (the last one, after a confirm re-run)."""
    status: Mapped[str] = mapped_column(Text)
    drift_details: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    ran_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ExportRow(Timestamps, Base):
    """One MP4 render of one workflow version with one preset (#124, docs/database-schema.md).

    Status only moves forward: queued -> rendering -> ready | failed, and ready -> expired when cleanup
    deletes the file (#125)."""

    __tablename__ = "exports"
    __table_args__ = (
        status_check("status", EXPORT_STATUSES, "status"),
        status_check("preset", EXPORT_PRESETS, "preset"),
        status_check("error_code", EXPORT_ERROR_CODES, "error_code"),
        # Re-use (D16): the same version, preset and voice that is queued, rendering or ready.
        Index(None, "workflow_id", "version_id", "preset", "voice"),
        Index(None, "status", "finished_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    """Who asked for it."""
    preset: Mapped[str] = mapped_column(Text)
    voice: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued", server_default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    video_key: Mapped[str | None] = mapped_column(Text, default=None)
    captions_key: Mapped[str | None] = mapped_column(Text, default=None)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)


class TutorialShareRow(Timestamps, Base):
    """A read-only share link to a workflow's tutorial (#96). The link holds a random token; only its SHA-256
    is stored, so the full link exists only in the owner's hands (phase-3-vishwas-share-tokens.md)."""

    __tablename__ = "tutorial_shares"
    __table_args__ = (Index(None, "workflow_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    """Null: never expires (the only choice in the MVP UI)."""
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)


class WorkflowStepRow(Timestamps, Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("version_id", "seq"),
        Index(None, "workflow_id"),
        status_check("risk", RISKS, "risk"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    """The version this step belongs to: every version has its own copy of every step."""
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[dict[str, Any]] = mapped_column()  # value masked if sensitive
    target: Mapped[dict[str, Any]] = mapped_column()
    instruction_text: Mapped[str] = mapped_column(Text)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    expected_state: Mapped[dict[str, Any]] = mapped_column()
    observed_state: Mapped[dict[str, Any]] = mapped_column()
    verification: Mapped[dict[str, Any]] = mapped_column()
    risk: Mapped[str] = mapped_column(Text)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    screenshot_path: Mapped[str | None] = mapped_column(Text, default=None)
    start_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    end_ms: Mapped[int | None] = mapped_column(Integer, default=None)

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
    Computed,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import REGCONFIG, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contracts_gen.common_schema import Language, PerformedBy, Risk
from app.contracts_gen.export_schema import ExportErrorCode, ExportPreset, ExportStatus
from app.contracts_gen.plan_schema import PlanStatus
from app.contracts_gen.run_schema import RunKind, RunStatus
from app.contracts_gen.task_schema import TaskStatus
from app.contracts_gen.workflow_schema import (
    TranslationStatus,
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
PERFORMED_BY = literal_values(PerformedBy)
LANGUAGES = literal_values(Language)
TRANSLATION_STATUSES = literal_values(TranslationStatus)
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
    title: Mapped[str | None] = mapped_column(Text, default=None)
    """The planner's general name for the tutorial (#390); the workflow's title. None: use the request."""
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


SEARCH_VECTOR = (
    "setweight(to_tsvector(lang, title), 'A') || setweight(to_tsvector('simple', target_app), 'A') || "
    "setweight(to_tsvector(lang, search_request), 'B') || setweight(to_tsvector(lang, search_steps), 'C')"
)
"""What a workflow is searched by (#135): title and app weigh most, then the request, then the step texts."""
SEARCH_TEXT = "title || ' ' || target_app || ' ' || search_request || ' ' || search_steps"
"""The same text for trigram matching (typos, partial words)."""


class WorkflowRow(Timestamps, Base):
    """A stored workflow: its identity (share links, tutorial URLs and reverify point here) plus copies of its
    current version's confidence, recording and viewport, so readers need one row. Its versions are
    `WorkflowVersionRow`s (docs/research/phase-4-decisions-alignment.md D1)."""

    __tablename__ = "workflows"
    __table_args__ = (
        status_check("status", WORKFLOW_STATUSES, "status"),
        Index(None, "target_app", "status"),
        Index(None, "user_id", "created_at"),
        # Search (#135, S1-S3): weighted full text, plus trigrams for typos and short titles.
        Index(None, "search", postgresql_using="gin"),
        Index(None, "title", postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
        Index(None, "search_text", postgresql_using="gin", postgresql_ops={"search_text": "gin_trgm_ops"}),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), unique=True)
    search_steps: Mapped[str] = mapped_column(Text, default="", server_default="")
    """The current version's step texts, one per line: copied by `refresh_search` (generated columns can't
    read other tables)."""
    search_request: Mapped[str] = mapped_column(Text, default="", server_default="")
    """The task's request, copied for search."""
    lang: Mapped[str] = mapped_column(
        REGCONFIG, default="english", server_default=text("'english'::regconfig")
    )
    """Text search language of title, request and steps (S3); per row, for translated text later (#132)."""
    search: Mapped[Any] = mapped_column(TSVECTOR, Computed(SEARCH_VECTOR, persisted=True))
    search_text: Mapped[str] = mapped_column(Text, Computed(SEARCH_TEXT, persisted=True))
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

    current_version: Mapped["WorkflowVersionRow | None"] = relationship(
        primaryjoin="WorkflowRow.current_version_id == WorkflowVersionRow.id",
        foreign_keys=[current_version_id],
        lazy="selectin",
        viewonly=True,
    )
    """The current version (read-only): its `source` tells whether a self-heal made it (#382)."""


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
    recorded_as: Mapped[str | None] = mapped_column(Text, default=None)
    """The site account the version was recorded in (ADR 0007); None before #404 (the shared test account)."""
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


class BrowserProfileRow(Timestamps, Base):
    """A user's own signed-in session on a site (#404, ADR 0007): the Playwright storage state,
    Fernet-encrypted with KRAMA_STORAGE_KEY. One per (user, site); deleted with the user."""

    __tablename__ = "browser_profiles"
    __table_args__ = (UniqueConstraint("user_id", "site"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    site: Mapped[str] = mapped_column(Text)
    account: Mapped[str] = mapped_column(Text)
    state: Mapped[bytes] = mapped_column(LargeBinary)
    """The encrypted storage state. Never logged, returned or sent anywhere."""
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(default=None)


class TranslationRow(Timestamps, Base):
    """A workflow version's title and step texts in one language (#422, L5): made once, on first request."""

    __tablename__ = "translations"
    __table_args__ = (
        UniqueConstraint("version_id", "language"),
        status_check("status", TRANSLATION_STATUSES, "status"),
        status_check("language", LANGUAGES, "language"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="translating", server_default="translating")
    title: Mapped[str | None] = mapped_column(Text, default=None)
    steps: Mapped[list[Any]] = mapped_column(default=list, server_default="[]")
    """[{step_seq, text, translated}] in step order."""
    error: Mapped[str | None] = mapped_column(Text, default=None)
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    """The translation prompt that made it (#448): an older one makes it again, in the background."""


class TranslationCacheRow(Base):
    """One translated text (L5): reused by every version and workflow with the same text, language and
    prompt."""

    __tablename__ = "translation_cache"

    text_sha: Mapped[str] = mapped_column(Text, primary_key=True)
    language: Mapped[str] = mapped_column(Text, primary_key=True)
    prompt_version: Mapped[str] = mapped_column(Text, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LLMCallRow(Base):
    """One request to one LLM model (#464): an attempt of a call, failed ones included, since they use quota
    too. No prompt or reply text (page content)."""

    __tablename__ = "llm_calls"
    __table_args__ = (Index("ix_llm_calls_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[UUID]
    attempt: Mapped[int] = mapped_column(Integer)
    job: Mapped[str] = mapped_column(Text)
    """The reply schema's name, e.g. LLMPlan, VisionBox, TaskAnswer."""
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    http_code: Mapped[int | None] = mapped_column(Integer, default=None)
    latency_ms: Mapped[int] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer, default=None)
    tokens_out: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ExportRow(Timestamps, Base):
    """One MP4 render of one workflow version with one preset (#124, docs/database-schema.md).

    Status only moves forward: queued -> rendering -> ready | failed, and ready -> expired when cleanup
    deletes the file (#125)."""

    __tablename__ = "exports"
    __table_args__ = (
        status_check("status", EXPORT_STATUSES, "status"),
        status_check("preset", EXPORT_PRESETS, "preset"),
        status_check("error_code", EXPORT_ERROR_CODES, "error_code"),
        status_check("language", LANGUAGES, "language"),
        # Re-use (D16): the same version, preset and voice that is queued, rendering or ready.
        Index(None, "workflow_id", "version_id", "preset", "voice", "language"),
        Index(None, "status", "finished_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    """Who asked for it."""
    preset: Mapped[str] = mapped_column(Text)
    voice: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, default="en", server_default="en")
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
        status_check("performed_by", PERFORMED_BY, "performed_by"),
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
    performed_by: Mapped[str] = mapped_column(Text, default="krama", server_default="krama")
    """human: the run's owner did this step in a takeover (ADR 0008)."""
    screenshot_path: Mapped[str | None] = mapped_column(Text, default=None)
    start_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    end_ms: Mapped[int | None] = mapped_column(Integer, default=None)

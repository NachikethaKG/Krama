"""workflow search

#416 (contract 1.17, #135): the text a workflow is searched by. `search_steps` (the current version's step
texts) and `search_request` (the task's request) are copies kept by `refresh_search`; `search` (weighted
tsvector) and `search_text` (for trigrams) are generated from them and the title. GIN indexes for both, and
pg_trgm. Existing workflows are backfilled here.

Revision ID: b8d23360c47b
Revises: 17eae8daacf9
Create Date: 2026-11-20 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d23360c47b"
down_revision: str | Sequence[str] | None = "17eae8daacf9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH = (
    "setweight(to_tsvector(lang, title), 'A') || setweight(to_tsvector('simple', target_app), 'A') || "
    "setweight(to_tsvector(lang, search_request), 'B') || setweight(to_tsvector(lang, search_steps), 'C')"
)
SEARCH_TEXT = "title || ' ' || target_app || ' ' || search_request || ' ' || search_steps"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("workflows", sa.Column("search_steps", sa.Text(), server_default="", nullable=False))
    op.add_column("workflows", sa.Column("search_request", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "workflows",
        sa.Column(
            "lang", postgresql.REGCONFIG(), server_default=sa.text("'english'::regconfig"), nullable=False
        ),
    )
    op.execute(
        """
        UPDATE workflows w SET
          search_request = coalesce((SELECT t.prompt FROM tasks t WHERE t.id = w.task_id), ''),
          search_steps = coalesce((
            SELECT string_agg(st.instruction_text, E'\n' ORDER BY st.seq)
            FROM workflow_steps st WHERE st.version_id = w.current_version_id
          ), '')
        """
    )
    op.add_column(
        "workflows",
        sa.Column("search", postgresql.TSVECTOR(), sa.Computed(SEARCH, persisted=True), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("search_text", sa.Text(), sa.Computed(SEARCH_TEXT, persisted=True), nullable=True),
    )
    op.create_index(op.f("ix_workflows_search"), "workflows", ["search"], postgresql_using="gin")
    op.create_index(
        op.f("ix_workflows_title"), "workflows", ["title"], postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )  # fmt: skip
    op.create_index(
        op.f("ix_workflows_search_text"), "workflows", ["search_text"], postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )  # fmt: skip


def downgrade() -> None:
    """Downgrade schema. pg_trgm stays (other things may use it)."""
    op.drop_index(op.f("ix_workflows_search_text"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_title"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_search"), table_name="workflows")
    op.drop_column("workflows", "search_text")
    op.drop_column("workflows", "search")
    op.drop_column("workflows", "lang")
    op.drop_column("workflows", "search_request")
    op.drop_column("workflows", "search_steps")

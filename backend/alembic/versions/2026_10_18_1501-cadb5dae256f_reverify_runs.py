"""reverify runs

runs.kind (task | reverify) and runs.source_workflow_id for POST /workflows/{id}/reverify (#77, contract
#253). Generated with autogenerate, then reviewed by hand: the kind CHECK is hand-written (autogenerate can't
see it). Existing runs become task runs through the server default.

Revision ID: cadb5dae256f
Revises: 6fa0e2f75269
Create Date: 2026-10-18 15:01:38.831964

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cadb5dae256f"
down_revision: str | Sequence[str] | None = "6fa0e2f75269"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("runs", sa.Column("kind", sa.Text(), server_default="task", nullable=False))
    op.create_check_constraint(op.f("ck_runs_kind"), "runs", "kind IN ('task', 'reverify')")
    op.add_column("runs", sa.Column("source_workflow_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_runs_source_workflow_id_workflows"),
        "runs",
        "workflows",
        ["source_workflow_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_runs_source_workflow_id_workflows"), "runs", type_="foreignkey")
    op.drop_column("runs", "source_workflow_id")
    op.drop_constraint(op.f("ck_runs_kind"), "runs", type_="check")
    op.drop_column("runs", "kind")

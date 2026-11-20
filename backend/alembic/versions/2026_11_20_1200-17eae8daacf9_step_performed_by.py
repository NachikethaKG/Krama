"""step performed by

#409 (contract 1.16, ADR 0008): workflow_steps.performed_by, krama or human (the run's owner did the step in a
takeover). Existing steps were all done by Krama (server default). Hand-written: the CHECK comes from the
generated PerformedBy enum.

Revision ID: 17eae8daacf9
Revises: f2d1fa67786a
Create Date: 2026-11-20 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17eae8daacf9"
down_revision: str | Sequence[str] | None = "f2d1fa67786a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "workflow_steps", sa.Column("performed_by", sa.Text(), server_default="krama", nullable=False)
    )
    op.create_check_constraint(
        op.f("ck_workflow_steps_performed_by"), "workflow_steps", "performed_by IN ('krama', 'human')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_workflow_steps_performed_by"), "workflow_steps", type_="check")
    op.drop_column("workflow_steps", "performed_by")

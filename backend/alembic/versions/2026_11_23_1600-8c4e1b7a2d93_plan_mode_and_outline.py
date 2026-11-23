"""plan mode and outline

#470, ADR 0011: a plan is either every step up front (upfront) or an outline the user approves, with the steps
decided during the run (steps). Existing plans are upfront.

Revision ID: 8c4e1b7a2d93
Revises: 5f2a8c1d9e47
Create Date: 2026-11-23 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c4e1b7a2d93"
down_revision: str | Sequence[str] | None = "5f2a8c1d9e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("plans", sa.Column("mode", sa.Text(), server_default="upfront", nullable=False))
    op.add_column("plans", sa.Column("outline", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("plans", "outline")
    op.drop_column("plans", "mode")

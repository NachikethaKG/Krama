"""plan title

#390 (contract #389): the planner's general name for the tutorial, which becomes the workflow's title instead of
the raw request. Nullable: older plans have none and keep using the request.

Revision ID: 5b1c0e7d9a42
Revises: ac684ed69930
Create Date: 2026-11-19 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b1c0e7d9a42"
down_revision: str | Sequence[str] | None = "ac684ed69930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("plans", sa.Column("title", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("plans", "title")

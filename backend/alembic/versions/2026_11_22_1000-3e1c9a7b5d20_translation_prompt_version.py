"""translation prompt version

#448: which translation prompt made a stored translation, so one made with an older prompt is made again.
Existing rows get NULL: older than any versioned prompt.

Revision ID: 3e1c9a7b5d20
Revises: afcc0795028c
Create Date: 2026-11-22 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e1c9a7b5d20"
down_revision: str | Sequence[str] | None = "afcc0795028c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("translations", sa.Column("prompt_version", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("translations", "prompt_version")

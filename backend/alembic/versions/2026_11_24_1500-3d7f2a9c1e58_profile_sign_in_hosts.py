"""profile sign-in hosts

#475, ADR 0012: the other hosts the owner opened while signing in to a site (an identity provider), stored with
the session. Existing profiles have none.

Revision ID: 3d7f2a9c1e58
Revises: 8c4e1b7a2d93
Create Date: 2026-11-24 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d7f2a9c1e58"
down_revision: str | Sequence[str] | None = "8c4e1b7a2d93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "browser_profiles",
        sa.Column(
            "sign_in_hosts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("browser_profiles", "sign_in_hosts")

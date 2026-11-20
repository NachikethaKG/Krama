"""user site sessions

#404 (contract 1.18, ADR 0007): browser_profiles (each user's own encrypted session per site), the account a
workflow version was recorded in (workflow_versions.recorded_as), and the `sign_in` run kind.

Revision ID: 91bd1a1957e7
Revises: b8d23360c47b
Create Date: 2026-11-20 17:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91bd1a1957e7"
down_revision: str | Sequence[str] | None = "b8d23360c47b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "browser_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("site", sa.Text(), nullable=False),
        sa.Column("account", sa.Text(), nullable=False),
        sa.Column("state", sa.LargeBinary(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_browser_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_browser_profiles")),
        sa.UniqueConstraint("user_id", "site", name=op.f("uq_browser_profiles_user_id_site")),
    )
    op.add_column("workflow_versions", sa.Column("recorded_as", sa.Text(), nullable=True))
    op.drop_constraint(op.f("ck_runs_kind"), "runs", type_="check")
    op.create_check_constraint(
        op.f("ck_runs_kind"), "runs", "kind IN ('task', 'reverify', 'do_it', 'sign_in')"
    )


def downgrade() -> None:
    """Downgrade schema. sign_in runs store nothing else, so they can go."""
    op.execute("DELETE FROM runs WHERE kind = 'sign_in'")
    op.drop_constraint(op.f("ck_runs_kind"), "runs", type_="check")
    op.create_check_constraint(op.f("ck_runs_kind"), "runs", "kind IN ('task', 'reverify', 'do_it')")
    op.drop_column("workflow_versions", "recorded_as")
    op.drop_table("browser_profiles")

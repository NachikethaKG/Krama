"""accounts and sessions

users and sessions for sign-in (#94, contract #287), and owners on tasks and workflows. Generated with
autogenerate, reviewed by hand. Existing tasks and workflows keep a null owner; `krama users seed --claim`
gives them to the demo account.

Revision ID: 411e150ecaac
Revises: cadb5dae256f
Create Date: 2026-10-24 12:08:09.484271

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "411e150ecaac"
down_revision: str | Sequence[str] | None = "cadb5dae256f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("failed_logins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_foreign_key(op.f("fk_tasks_user_id_users"), "tasks", "users", ["user_id"], ["id"])
    op.add_column("workflows", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_workflows_user_id_created_at"), "workflows", ["user_id", "created_at"], unique=False
    )
    op.create_foreign_key(op.f("fk_workflows_user_id_users"), "workflows", "users", ["user_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_workflows_user_id_users"), "workflows", type_="foreignkey")
    op.drop_index(op.f("ix_workflows_user_id_created_at"), table_name="workflows")
    op.drop_column("workflows", "user_id")
    op.drop_constraint(op.f("fk_tasks_user_id_users"), "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")

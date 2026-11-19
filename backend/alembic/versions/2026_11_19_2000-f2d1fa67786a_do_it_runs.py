"""do it runs

#399 (contract for #129): runs.kind gains 'do_it', a stored verified workflow run for its owner with their own
values. The kind CHECK is built from the generated RunKind enum, so it is widened in the contract PR itself
(test_status_checks_match_the_contract). Hand-written: autogenerate can't see a CHECK.

Revision ID: f2d1fa67786a
Revises: 5b1c0e7d9a42
Create Date: 2026-11-19 20:00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2d1fa67786a"
down_revision: str | Sequence[str] | None = "5b1c0e7d9a42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f("ck_runs_kind"), "runs", type_="check")
    op.create_check_constraint(op.f("ck_runs_kind"), "runs", "kind IN ('task', 'reverify', 'do_it')")


def downgrade() -> None:
    """Downgrade schema. do_it runs store no workflow, so they can go; their events cascade."""
    op.execute("DELETE FROM runs WHERE kind = 'do_it'")
    op.drop_constraint(op.f("ck_runs_kind"), "runs", type_="check")
    op.create_check_constraint(op.f("ck_runs_kind"), "runs", "kind IN ('task', 'reverify')")

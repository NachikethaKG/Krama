"""translations

#422/#428 (contract 1.19, #132): a workflow version's texts per language (translations), the cache of single
translated texts (translation_cache), and the language of an export.

Revision ID: afcc0795028c
Revises: 91bd1a1957e7
Create Date: 2026-11-20 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "afcc0795028c"
down_revision: str | Sequence[str] | None = "91bd1a1957e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LANGUAGES = "('en', 'hi', 'kn', 'de', 'es', 'fr')"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="translating", nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('translating', 'ready', 'failed')", name=op.f("ck_translations_status")
        ),
        sa.CheckConstraint(f"language IN {LANGUAGES}", name=op.f("ck_translations_language")),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_translations_workflow_id_workflows"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["workflow_versions.id"],
            name=op.f("fk_translations_version_id_workflow_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translations")),
        sa.UniqueConstraint("version_id", "language", name=op.f("uq_translations_version_id_language")),
    )
    op.create_table(
        "translation_cache",
        sa.Column("text_sha", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("text_sha", "language", "prompt_version", name=op.f("pk_translation_cache")),
    )
    op.add_column("exports", sa.Column("language", sa.Text(), server_default="en", nullable=False))
    op.create_check_constraint(op.f("ck_exports_language"), "exports", f"language IN {LANGUAGES}")
    op.drop_index(op.f("ix_exports_workflow_id_version_id_preset_voice"), table_name="exports")
    op.create_index(
        op.f("ix_exports_workflow_id_version_id_preset_voice_language"),
        "exports",
        ["workflow_id", "version_id", "preset", "voice", "language"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_exports_workflow_id_version_id_preset_voice_language"), table_name="exports")
    op.create_index(
        op.f("ix_exports_workflow_id_version_id_preset_voice"),
        "exports",
        ["workflow_id", "version_id", "preset", "voice"],
    )
    op.drop_constraint(op.f("ck_exports_language"), "exports", type_="check")
    op.drop_column("exports", "language")
    op.drop_table("translation_cache")
    op.drop_table("translations")

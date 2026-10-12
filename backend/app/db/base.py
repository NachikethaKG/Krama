"""Declarative base: timestamptz everywhere, JSONB for documents, stable constraint names, status CHECKs."""

from datetime import datetime
from typing import Any, ClassVar, get_args

from sqlalchemy import CheckConstraint, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Alembic needs stable names to drop or change a constraint later; autogenerate does NOT notice a changed
# CHECK (docs/research/phase-1-vishwas-database.md), so status changes are hand-written migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # A plain Mapped[datetime] would be `timestamp without time zone`; the schema says timestamptz.
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


def literal_values(alias: Any) -> tuple[str, ...]:
    """The values of a generated contract status alias, e.g. `RunStatus` → ('queued', 'running', …)."""
    literal = get_args(alias.__value__)[0]
    return tuple(get_args(literal))


def status_check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """`column IN (...)` with a stable name. Text + CHECK, not a Postgres ENUM: ENUMs are hard to change."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name)

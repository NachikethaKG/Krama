"""`krama llm-usage`: LLM requests per day, model and status (#464), from the `llm_calls` table.

uv run krama llm-usage            # the last 7 days
uv run krama llm-usage --days 30

Every request is counted, failed ones too: a 429 or a 503 still uses the free-tier quota.
"""

import argparse
import asyncio
from collections import defaultdict
from datetime import date

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.db.llm_calls import UsageRow, usage


def add_parser(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = commands.add_parser("llm-usage", help="LLM requests per day and model", description=__doc__)
    p.add_argument("--days", type=int, default=7, help="how many days back (default 7)")


def llm_usage_command(args: argparse.Namespace) -> int:
    rows = asyncio.run(_load(args.days))
    print(format_usage(rows) if rows else f"No LLM requests recorded in the last {args.days} days.")
    return 0


async def _load(days: int) -> list[UsageRow]:
    engine = create_engine(get_settings().database_url)
    try:
        return await usage(create_sessionmaker(engine), days=days)
    finally:
        await engine.dispose()


def format_usage(rows: list[UsageRow]) -> str:
    """One line per day and model: total requests, then each status, then tokens."""
    grouped: dict[tuple[date, str], list[UsageRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.day, row.model)].append(row)
    lines = []
    for (day, model), parts in grouped.items():
        total = sum(p.requests for p in parts)
        statuses = ", ".join(f"{p.status} {p.requests}" for p in parts)
        tokens_in = sum(p.tokens_in for p in parts)
        tokens_out = sum(p.tokens_out for p in parts)
        tokens = f"tokens {tokens_in} in, {tokens_out} out"
        lines.append(f"{day}  {model:24} {total:4} requests ({statuses}); {tokens}")
    return "\n".join(lines)

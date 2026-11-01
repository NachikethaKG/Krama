"""`krama exports ...`: maintenance of MP4 exports (#125).

uv run krama exports cleanup            # expire old exports, enforce EXPORTS_MAX_GB, drop unused clips
uv run krama exports cleanup --dry-run  # only report what would go

The worker (`just backend worker`) runs the same cleanup every day at 03:30.
"""

import argparse
import asyncio

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.storage import LocalFsStore
from app.storage.cleanup import cleanup_with_settings


def add_parser(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    exports = commands.add_parser("exports", help="maintenance of MP4 exports", description=__doc__)
    exports.add_argument("action", choices=["cleanup"])
    exports.add_argument(
        "--dry-run", action="store_true", help="report what would be deleted, delete nothing"
    )


def exports_command(args: argparse.Namespace) -> int:
    return asyncio.run(_cleanup(dry_run=args.dry_run))


async def _cleanup(*, dry_run: bool) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        report = await cleanup_with_settings(
            settings, create_sessionmaker(engine), LocalFsStore(settings.artifacts_dir), dry_run=dry_run
        )
    finally:
        await engine.dispose()
    print(("Dry run: " if dry_run else "") + report.summary())
    for key in report.deleted_files:
        print(f"  {'would delete' if dry_run else 'deleted'} {key}")
    for key in report.busy:
        print(f"  busy, kept for next time: {key}")
    return 0

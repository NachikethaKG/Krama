"""`krama validate`: one pass of scheduled validation by hand (#110), without the worker.

uv run krama validate                  # the workflows that are due (every 7 days, back-off after blocked)
uv run krama validate --workflow ID    # this one now, whatever its schedule

Each replay first resets what the workflow creates on its site (Gitea, the GitHub test org), like a reverify.
The worker does the same every 30 min when VALIDATION_ENABLED=true.
"""

import argparse
import asyncio
from uuid import UUID

from app.api.services import build_run_environment
from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.runs import InProcessExecutor, RunStore
from app.runs.validation_backend import RunValidationBackend
from app.targets import target_setup
from app.validation import RedisSiteLimits, ScheduledValidator


def add_parser(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    validate = commands.add_parser(
        "validate",
        help="re-check stored workflows now",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    validate.add_argument("--workflow", type=UUID, help="validate this workflow now, whatever its schedule")


def validate_command(args: argparse.Namespace) -> int:
    return asyncio.run(_validate(args.workflow))


async def _validate(workflow_id: UUID | None) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    sessions = create_sessionmaker(engine)
    executor = InProcessExecutor(RunStore(sessions), build_run_environment(settings))
    backend = RunValidationBackend(sessions, executor, lambda url: target_setup(url, settings))
    validator = ScheduledValidator(backend, RedisSiteLimits(settings.redis_url))
    try:
        if workflow_id is None:
            print(f"Validated {await validator.run_due()} workflow(s).")
            return 0
        candidate = next((c for c in await backend.candidates() if c.workflow_id == workflow_id), None)
        if candidate is None:
            print(f"No replayable workflow {workflow_id} (only gitea and github workflows are validated).")
            return 1
        record = await validator.validate(candidate)
        print(f"{record.status}: {record.drift_details}")
        return 0
    finally:
        await executor.shutdown()
        await engine.dispose()

"""Runs: execute an approved plan step by step, observe and verify each step, and record what happened.

`krama run` (runner.py) runs one task in the terminal. The API runs approved plans in the background with
`InProcessExecutor` (executor.py), persisting every transition through `RunStore`; the state table is in
states.py.
"""

from app.runs.executor import InProcessExecutor, RunEnvironment, RunExecutor
from app.runs.report import ObservedSummary, RunReport, RunStatus, StepReport
from app.runs.runner import RunOptions, RunParts, run_task
from app.runs.store import RunJob, RunNotFoundError, RunStore

__all__ = [
    "InProcessExecutor",
    "ObservedSummary",
    "RunEnvironment",
    "RunExecutor",
    "RunJob",
    "RunNotFoundError",
    "RunOptions",
    "RunParts",
    "RunReport",
    "RunStatus",
    "RunStore",
    "StepReport",
    "run_task",
]

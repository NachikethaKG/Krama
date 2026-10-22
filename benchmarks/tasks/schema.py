"""Typed schema models and YAML loader for benchmark tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskFormatError(ValueError):
    """Raised when a task file contains malformed YAML or invalid structure."""


class ApiCall(BaseModel):
    """One HTTP request against the target's API, sent as the demo user (benchmarks/tasks/runner.py).

    `url` is a path on the task's API (`/api/v1/...` on Gitea, `/repos/...` on GitHub). `{user}` stands for
    the signed-in account's name and `{org}` for the GitHub test organization (GITHUB_TEST_ORG).
    """

    model_config = ConfigDict(extra="forbid")

    method: str = Field(default="GET", description="HTTP method")
    url: str = Field(min_length=1, description="Path on the target, e.g. /api/v1/repos/{user}/x")
    body: dict[str, Any] | None = Field(default=None, description="JSON body")
    ok_status: list[int] = Field(
        default_factory=lambda: [200, 201, 204],
        description="Statuses that count as done (e.g. add 404 for a delete of something absent)",
    )


class SetupConfig(BaseModel):
    """Optional pre-run environment setup and teardown configuration."""

    model_config = ConfigDict(extra="forbid")

    command: str | None = Field(
        default=None, description="Shell command for pre-run reset"
    )
    api_call: dict[str, Any] | None = Field(
        default=None, description="Structured API request parameters for reset"
    )
    api_calls: list[ApiCall] = Field(
        default_factory=list,
        description="Requests run in order before every trial, e.g. delete then re-create a repo",
    )


class SuccessCheckConfig(BaseModel):
    """Deterministic validation check proving task completion."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Verification type: api, command, or dom")
    assertion: dict[str, Any] | str = Field(
        description="Assertion definition for success check"
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("success_check type must not be empty")
        if clean not in {"api", "command", "dom"}:
            raise ValueError(
                f"Unsupported success_check type '{v}', expected 'api', 'command', or 'dom'"
            )
        return clean


class BenchmarkTask(BaseModel):
    """Standardized single-file benchmark task specification."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Unique task identifier")
    prompt: str = Field(min_length=1, description="Instructions provided to the agent")
    target: str = Field(
        min_length=1, description="Target application URL or identifier"
    )
    site: Literal["gitea", "github"] = Field(
        default="gitea",
        description="Whose API the setup and check call, and how they sign in: Gitea's demo user (basic "
        "auth) or the GitHub test account's token (GITHUB_BENCH_TOKEN)",
    )
    api_base: str | None = Field(
        default=None,
        description="API root when it isn't the target, e.g. https://api.github.com for target https://github.com",
    )
    setup: SetupConfig | None = Field(
        default=None, description="Pre-run environment reset hook"
    )
    success_check: SuccessCheckConfig = Field(
        description="Independent functional verification check"
    )


TaskSpec = BenchmarkTask


def load_task_from_yaml(source: str | Path) -> BenchmarkTask:
    """Load and validate a benchmark task from a file path or raw YAML string."""
    if isinstance(source, Path) or (
        isinstance(source, str) and "\n" not in source and Path(source).exists()
    ):
        path = Path(source)
        content = path.read_text(encoding="utf-8")
    else:
        content = str(source)

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise TaskFormatError(f"Malformed YAML task definition: {exc}") from exc

    if not isinstance(data, dict):
        raise TaskFormatError(
            f"Task definition must be a YAML mapping/dictionary, got {type(data).__name__}"
        )

    return BenchmarkTask.model_validate(data)


def load_all_tasks(tasks_dir: Path | None = None) -> list[BenchmarkTask]:
    """Scan a directory and load all *.yaml / *.yml benchmark tasks."""
    directory = tasks_dir or Path(__file__).resolve().parent
    tasks: list[BenchmarkTask] = []

    for file_path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        tasks.append(load_task_from_yaml(file_path))

    return tasks

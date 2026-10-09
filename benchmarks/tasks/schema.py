"""Typed schema models and YAML loader for benchmark tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskFormatError(ValueError):
    """Raised when a task file contains malformed YAML or invalid structure."""


class SetupConfig(BaseModel):
    """Optional pre-run environment setup and teardown configuration."""

    model_config = ConfigDict(extra="forbid")

    command: str | None = Field(
        default=None, description="Shell command for pre-run reset"
    )
    api_call: dict[str, Any] | None = Field(
        default=None, description="Structured API request parameters for reset"
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

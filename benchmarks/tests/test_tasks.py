from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmarks.tasks import (
    BenchmarkTask,
    SetupConfig,
    SuccessCheckConfig,
    TaskFormatError,
    TaskSpec,
    load_all_tasks,
    load_task_from_yaml,
)


def test_task_model_direct_instantiation() -> None:
    task = BenchmarkTask(
        name="custom-task",
        prompt="Do something useful",
        target="http://localhost:3000",
        setup=SetupConfig(command="echo reset"),
        success_check=SuccessCheckConfig(
            type="api",
            assertion={
                "method": "GET",
                "url": "http://localhost:3000/api",
                "expected_status": 200,
            },
        ),
    )
    assert task.name == "custom-task"
    assert task.prompt == "Do something useful"
    assert task.target == "http://localhost:3000"
    assert task.setup is not None
    assert task.setup.command == "echo reset"
    assert task.success_check.type == "api"
    assert isinstance(task.success_check.assertion, dict)


def test_task_spec_alias() -> None:
    assert TaskSpec is BenchmarkTask


def test_load_all_tasks_discovers_canonical_tasks() -> None:
    tasks_dir = Path(__file__).resolve().parents[1] / "tasks"
    tasks = load_all_tasks(tasks_dir)
    assert len(tasks) >= 1

    task_names = [t.name for t in tasks]
    assert "gitea-create-repo" in task_names


def test_gitea_create_repo_task_schema_conformance() -> None:
    task_file = Path(__file__).resolve().parents[1] / "tasks" / "gitea-create-repo.yaml"
    assert task_file.exists()

    task = load_task_from_yaml(task_file)
    assert task.name == "gitea-create-repo"
    assert "Create a new public repository" in task.prompt
    assert "test-repo" in task.prompt
    assert task.target == "http://localhost:3000"

    assert task.setup is not None
    assert task.setup.command is not None
    assert "curl" in task.setup.command
    assert "test-repo" in task.setup.command

    assert task.success_check.type == "api"
    assert isinstance(task.success_check.assertion, dict)
    assert task.success_check.assertion["method"] == "GET"
    assert "test-repo" in task.success_check.assertion["url"]
    assert task.success_check.assertion["expected_status"] == 200


def test_load_task_from_raw_yaml_string() -> None:
    raw_yaml = """
name: test-inline
prompt: "Test prompt instructions"
target: "http://localhost:8080"
success_check:
  type: command
  assertion: "exit 0"
"""
    task = load_task_from_yaml(raw_yaml)
    assert task.name == "test-inline"
    assert task.prompt == "Test prompt instructions"
    assert task.target == "http://localhost:8080"
    assert task.setup is None
    assert task.success_check.type == "command"
    assert task.success_check.assertion == "exit 0"


def test_validation_error_missing_required_fields() -> None:
    # Missing prompt
    with pytest.raises(ValidationError, match="Field required"):
        BenchmarkTask.model_validate(
            {
                "name": "no-prompt",
                "target": "http://localhost:3000",
                "success_check": {"type": "command", "assertion": "exit 0"},
            }
        )

    # Missing target
    with pytest.raises(ValidationError, match="Field required"):
        BenchmarkTask.model_validate(
            {
                "name": "no-target",
                "prompt": "Do it",
                "success_check": {"type": "command", "assertion": "exit 0"},
            }
        )

    # Missing success_check
    with pytest.raises(ValidationError, match="Field required"):
        BenchmarkTask.model_validate(
            {
                "name": "no-check",
                "prompt": "Do it",
                "target": "http://localhost:3000",
            }
        )


def test_validation_error_invalid_success_check_type() -> None:
    with pytest.raises(ValidationError, match="Unsupported success_check type"):
        BenchmarkTask.model_validate(
            {
                "name": "invalid-type",
                "prompt": "Do it",
                "target": "http://localhost:3000",
                "success_check": {"type": "magic_check", "assertion": "ok"},
            }
        )


def test_validation_error_extra_forbidden_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BenchmarkTask.model_validate(
            {
                "name": "extra-fields",
                "prompt": "Do it",
                "target": "http://localhost:3000",
                "extra_field": "not_allowed",
                "success_check": {"type": "command", "assertion": "exit 0"},
            }
        )


def test_validation_error_malformed_yaml() -> None:
    bad_yaml = "name: broken\n  prompt: indentation_error\n    bad:"
    with pytest.raises(TaskFormatError, match="Malformed YAML"):
        load_task_from_yaml(bad_yaml)


def test_validation_error_non_dictionary_yaml() -> None:
    with pytest.raises(TaskFormatError, match="mapping/dictionary"):
        load_task_from_yaml("- a\n- list\n- instead")

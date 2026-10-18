"""`python -m benchmarks.tasks list | setup <task> | check <task>`: reset Gitea for a task or grade it."""

from __future__ import annotations

import sys

from benchmarks.tasks.runner import TaskSetupError, check_success, run_setup
from benchmarks.tasks.schema import load_all_tasks


def main(argv: list[str]) -> int:
    tasks = {t.name: t for t in load_all_tasks()}
    if not argv or argv[0] == "list":
        for name, task in tasks.items():
            print(f"{name}: {task.prompt}")
        return 0
    if len(argv) != 2 or argv[0] not in ("setup", "check") or argv[1] not in tasks:
        print("usage: python -m benchmarks.tasks list | setup <task> | check <task>")
        print(f"tasks: {', '.join(tasks)}")
        return 2
    task = tasks[argv[1]]
    if argv[0] == "setup":
        try:
            for line in run_setup(task):
                print(line)
        except TaskSetupError as e:
            print(f"setup failed: {e}")
            return 1
        return 0
    result = check_success(task)
    print(("PASS " if result.passed else "FAIL ") + result.detail)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

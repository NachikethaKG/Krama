"""Proves the typed conformance pattern works: mypy must reject an implementation that drifts from a port."""

from pathlib import Path

from mypy import api

BACKEND = Path(__file__).resolve().parents[2]

DRIFTED_POLICY = """
from app.ports import Policy, PageState, StepRef

class DriftedPolicy:
    async def assess_plan(self, plan: object) -> object: ...
    async def check_action(self, step: StepRef) -> bool: ...  # missing `page`, wrong return type
    def mask(self, observed: object) -> object: ...

_: Policy = DriftedPolicy()
"""


def test_mypy_rejects_a_policy_that_drifts_from_the_port(tmp_path: Path) -> None:
    source = tmp_path / "drifted.py"
    source.write_text(DRIFTED_POLICY, encoding="utf-8")

    stdout, _, status = api.run(
        [str(source), "--config-file", str(BACKEND / "pyproject.toml"), "--no-incremental"]
    )

    assert status != 0
    assert 'expression has type "DriftedPolicy", variable has type "Policy"' in stdout


def test_mypy_accepts_the_fakes() -> None:
    stdout, _, status = api.run(
        [str(BACKEND / "app" / "ports"), "--config-file", str(BACKEND / "pyproject.toml"), "--no-incremental"]
    )

    assert status == 0, stdout

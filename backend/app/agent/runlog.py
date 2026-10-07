import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.agent.executor import ActionExecutor, ActionResult
from app.contracts_gen.common_schema import Action, Target

MASK = "***"
# Fill values for fields with these names are never written to a run log (AGENTS.md §4).
_SENSITIVE_NAME = re.compile(
    r"pass(word|code|phrase)?|secret|token|api.?key|otp|pin\b|cvv|card", re.IGNORECASE
)

type Section = Literal["precondition", "step"]


class ScriptedStep(BaseModel):
    """One hand-written action. `section` separates setup (like logging in) from the task's own steps."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Action
    target: Target | None = None
    section: Section = "step"
    sensitive: bool = False
    """Mask the action's value in the run log. Also applied automatically to password-like field names."""


class RunLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seq: int = Field(ge=1)
    section: Section
    action: Action
    target: Target | None
    result: ActionResult


class RunLog(BaseModel):
    """What happened in one run: every action, its timing and its result. Saved as JSON with the artifacts."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    task: str
    base_url: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    ok: bool = False
    entries: list[RunLogEntry] = []

    @property
    def failed_entry(self) -> RunLogEntry | None:
        return next((e for e in self.entries if not e.result.ok), None)

    def write(self, artifacts_dir: Path) -> Path:
        """Write `<artifacts_dir>/runs/<run_id>/run-log.json` and return its path."""
        path = artifacts_dir / "runs" / str(self.run_id) / "run-log.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def is_sensitive(step: ScriptedStep) -> bool:
    name = step.target.name if step.target is not None else None
    return step.sensitive or bool(name and _SENSITIVE_NAME.search(name))


async def run_script(
    executor: ActionExecutor, steps: list[ScriptedStep], *, task: str, base_url: str
) -> RunLog:
    """Run `steps` in order and stop at the first failed action. Never raises for a failed action."""
    log = RunLog(task=task, base_url=base_url, started_at=datetime.now(UTC))
    t0 = time.perf_counter()
    for seq, step in enumerate(steps, start=1):
        result = await executor.execute(step.action, step.target)
        logged_action = step.action
        if is_sensitive(step) and step.action.value is not None:
            logged_action = step.action.model_copy(update={"value": MASK})
        log.entries.append(
            RunLogEntry(
                seq=seq, section=step.section, action=logged_action, target=step.target, result=result
            )
        )
        if not result.ok:
            break
    log.ok = len(log.entries) == len(steps) and all(e.result.ok for e in log.entries)
    log.finished_at = datetime.now(UTC)
    log.duration_ms = round((time.perf_counter() - t0) * 1000)
    return log

from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.agent.executor import ActionResult
from app.agent.runlog import RunLogEntry
from app.contracts_gen.common_schema import Action, Risk, Target
from app.contracts_gen.plan_schema import Plan
from app.llm import LLMAttempt
from app.ports.models import RecordingRef
from app.verifier import VerificationOutcome

type RunStatus = Literal["verified", "failed", "rejected", "needs_clarification", "error"]


class ObservedSummary(BaseModel):
    """What the observer saw after a step (the full ARIA text stays out of the log; screenshots are files)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    title: str
    screenshot_path: str | None = None


class StepReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seq: int
    instruction_text: str
    action: Action
    """The planned action; fill values of password-like fields are `***`."""
    target: Target
    risk: Risk
    result: ActionResult
    observed: ObservedSummary | None = None
    verification: VerificationOutcome | None = None
    verify_attempts: int = 0


class RunReport(BaseModel):
    """The run log of `krama run`: plan, every action, what was observed and how each step was verified."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    task: str
    target_url: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    status: RunStatus = "error"
    message: str = ""
    plan: Plan | None = None
    planner_model: str | None = None
    llm_attempts: list[LLMAttempt] = []
    preconditions: list[RunLogEntry] = []
    steps: list[StepReport] = []
    recording: RecordingRef | None = None

    @property
    def ok(self) -> bool:
        return self.status == "verified"

    def run_dir(self, artifacts_dir: Path) -> Path:
        return artifacts_dir / "runs" / str(self.run_id)

    def write(self, artifacts_dir: Path) -> Path:
        """Write `<artifacts_dir>/runs/<run_id>/run-log.json` and return its path."""
        path = self.run_dir(artifacts_dir) / "run-log.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

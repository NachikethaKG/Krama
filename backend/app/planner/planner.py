import re
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.contracts_gen.common_schema import Risk
from app.contracts_gen.plan_schema import Plan, PlannedStep
from app.llm import LLMAttempt, LLMProvider
from app.planner.prompt import SYSTEM_PROMPT, build_prompt

_RISK_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
_NEEDS_TARGET = frozenset({"click", "fill", "select"})
_NEEDS_VALUE = frozenset({"fill", "select", "navigate", "press"})


class LLMPlan(BaseModel):
    """What the LLM fills in. Ids, revision, status and timestamps are added by our code."""

    model_config = ConfigDict(extra="forbid")

    expected_result: str
    steps: list[PlannedStep]
    clarification_question: str | None = None


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: UUID
    task: str = Field(min_length=1)
    start_path: str = "/"
    page_snapshot: str = ""
    """ARIA snapshot of the start page. Untrusted; redacted again before it reaches the LLM."""
    site: str | None = None
    signed_in_as: str | None = None


class PlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan: Plan
    model: str
    llm_attempts: list[LLMAttempt]
    """Every LLM request it took, including failed ones and retries (for the run log and the benchmark)."""


class PlannerError(Exception):
    def __init__(self, message: str, llm_attempts: list[LLMAttempt] | None = None) -> None:
        super().__init__(message)
        self.llm_attempts = llm_attempts or []


class NeedsClarificationError(PlannerError):
    """The task is ambiguous or impossible; `question` goes back to the user (task needs_clarification)."""

    def __init__(self, question: str, llm_attempts: list[LLMAttempt] | None = None) -> None:
        super().__init__(f"needs clarification: {question}", llm_attempts)
        self.question = question


class InvalidPlanError(PlannerError):
    """The LLM's plan broke the rules below, also after one retry with the reasons."""

    def __init__(self, problems: list[str], llm_attempts: list[LLMAttempt] | None = None) -> None:
        super().__init__("invalid plan: " + "; ".join(problems), llm_attempts)
        self.problems = problems


class Planner(Protocol):
    async def plan(self, request: PlanRequest) -> PlanResult: ...


class LLMPlanner:
    """Task → contract-valid `Plan` with `instruction_text` and `expected_state` per step."""

    def __init__(self, llm: LLMProvider, *, max_attempts: int = 2) -> None:
        self._llm = llm
        self._max_attempts = max_attempts

    async def plan(self, request: PlanRequest) -> PlanResult:
        attempts: list[LLMAttempt] = []
        feedback: str | None = None
        problems: list[str] = []
        for _ in range(self._max_attempts):
            prompt = build_prompt(
                request.task,
                start_path=request.start_path,
                page_snapshot=request.page_snapshot,
                site=request.site,
                signed_in_as=request.signed_in_as,
                feedback=feedback,
            )
            result = await self._llm.generate(system=SYSTEM_PROMPT, prompt=prompt, schema=LLMPlan)
            attempts += result.attempts
            draft = result.value
            if draft.clarification_question and not draft.steps:
                raise NeedsClarificationError(draft.clarification_question, attempts)
            problems = check_steps(draft)
            if not problems:
                return PlanResult(
                    plan=to_plan(draft, request.task_id), model=result.model, llm_attempts=attempts
                )
            feedback = "\n".join(f"- {p}" for p in problems)
        raise InvalidPlanError(problems, attempts)


class StaticPlanner:
    """Returns a fixed plan (with fresh ids) so the executor and API can be built before planning is good."""

    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    async def plan(self, request: PlanRequest) -> PlanResult:
        plan = self._plan.model_copy(
            update={"id": uuid4(), "task_id": request.task_id, "created_at": datetime.now(UTC)}
        )
        return PlanResult(plan=plan, model="static", llm_attempts=[])


def check_steps(draft: LLMPlan) -> list[str]:
    """Rules the contract can't express (or the generated models don't enforce)."""
    problems: list[str] = []
    if not draft.steps:
        problems.append("the plan has no steps")
    if not draft.expected_result.strip():
        problems.append("expected_result is empty")
    for i, step in enumerate(draft.steps, start=1):
        where = f"step {i}"
        state = step.expected_state
        if not state.model_dump(exclude_none=True, exclude_defaults=True):
            problems.append(f"{where}: expected_state needs at least one condition")
        if state.url_matches is not None:
            if "://" in state.url_matches or state.url_matches.lstrip("^").startswith(("http", "www.")):
                problems.append(f"{where}: url_matches must be a path regex, not a full URL")
            try:
                re.compile(state.url_matches)
            except re.error as e:
                problems.append(f"{where}: url_matches is not a valid regex ({e})")
        has_target = bool(step.target.role or step.target.selector)
        if step.action.type in _NEEDS_TARGET and not has_target:
            problems.append(f"{where}: {step.action.type} needs a target role or selector")
        if step.action.type in _NEEDS_VALUE and step.action.value is None:
            problems.append(f"{where}: {step.action.type} needs a value")
        if step.action.type == "navigate" and not (step.action.value or "").startswith("/"):
            problems.append(f"{where}: navigate takes a URL path starting with '/'")
        if not step.instruction_text.strip():
            problems.append(f"{where}: instruction_text is empty")
    return problems


def to_plan(draft: LLMPlan, task_id: UUID) -> Plan:
    steps = [s.model_copy(update={"seq": i}) for i, s in enumerate(draft.steps, start=1)]
    risk: Risk = max((s.risk for s in steps), key=lambda r: _RISK_ORDER[r])
    return Plan(
        id=uuid4(),
        task_id=task_id,
        revision=1,
        status="proposed",
        risk=risk,
        expected_result=draft.expected_result,
        steps=steps,
        created_at=datetime.now(UTC),
    )

"""Look before each step (ADR 0011): an outline the user approves (#467), then one decision per step (#468).

The outline names rough intentions only: no selectors and no expected states, since nobody has seen those
pages yet. During the run, the decider looks at the current page and picks one action toward the outline;
what the action changed becomes the step's expected state (app/verifier/change.py). Page text is untrusted
data in a delimited block, never instructions (AGENTS.md §4).
"""

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.contracts_gen.common_schema import Action, ExpectedState, Risk, Target
from app.contracts_gen.plan_schema import OutlineItem, Plan, PlannedStep
from app.llm import UNTRUSTED_DATA_RULE, LLMAttempt, LLMProvider, neutralize_tags, untrusted_block
from app.planner.instructions import tutorial_text
from app.planner.planner import NeedsClarificationError, PlannerError, PlanRequest, PlanResult
from app.planner.prompt import build_prompt, redact_snapshot

MAX_OUTLINE_ITEMS = 8

OUTLINE_SYSTEM = "\n".join(
    [
        "You outline browser tasks for a tutorial engine. A human approves your outline; then an agent",
        "does the task one step at a time, looking at each page before it acts.",
        "",
        "Rules:",
        f'- Write 1 to {MAX_OUTLINE_ITEMS} short intentions in order, each starting with a verb: "Open the',
        '  search", "Search for the place", "Open the first result". No element names you haven\'t seen,',
        "  no selectors, no URLs, no expected results per item.",
        "- Use only what the task asks; stop when it is done. Never add sign-in, payment or deleting",
        "  unless the task asks for it.",
        "- risk for the whole task: low for looking and searching, medium for creating or changing",
        "  something, high for deleting, transferring, publishing, sending, paying or changing security",
        "  settings.",
        "- expected_result: one sentence describing the final state. title: the tutorial's name, at most 8",
        "  words, starting with a verb, general (no account, user, repository or other names from the task).",
        "- The tutorial teaches anyone: items never name the account or values a learner would replace.",
        "  Made-up example names end with the example suffix you are given.",
        "- Ask in clarification_question (with no outline) only when WHAT to do is unclear or impossible on",
        "  this site.",
        UNTRUSTED_DATA_RULE,
    ]
)

DECIDE_SYSTEM = "\n".join(
    [
        "You operate a web browser for a user, one step at a time. You get the task, its outline, the steps",
        "already done, and the current page as an ARIA snapshot. Decide the single next action.",
        "",
        "Rules:",
        "- Use only elements in the snapshot, with their exact role and accessible name.",
        "- Actions: click (buttons, links, checkboxes, tabs, menu items), fill (type into a field;",
        "  value = the text), select (value = the option), press (a key in a field; value = the key, e.g.",
        "  Enter), navigate (value = a URL path starting with /, only when no link or button gets there),",
        "  wait.",
        "- If the whole task is already complete on this page, answer done.",
        "- thought: one short sentence: what the page shows and why this action.",
        "- outline_seq: the outline item this action works on.",
        "- risk: low for looking, typing and navigating; medium for creating something; high for deleting,",
        "  transferring, publishing, sending, paying or changing security settings.",
        "- Made-up example values end with the example suffix you are given; values the task names are used",
        "  exactly.",
        UNTRUSTED_DATA_RULE,
    ]
)


class LLMOutline(BaseModel):
    """What the LLM fills in for an outline."""

    model_config = ConfigDict(extra="forbid")

    expected_result: str
    title: str | None = None
    outline: list[str]
    risk: Risk
    clarification_question: str | None = None


class DecidedTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(description="ARIA role from the snapshot")
    name: str = Field(description="accessible name, exactly as in the snapshot")


class LLMDecision(BaseModel):
    """What the LLM fills in for one step."""

    model_config = ConfigDict(extra="forbid")

    thought: str
    outline_seq: int | None = None
    action: Literal["click", "fill", "select", "press", "check", "navigate", "wait", "done"]
    target: DecidedTarget | None = None
    value: str | None = None
    risk: Risk = "low"


class StepContext(BaseModel):
    """What the decider sees. `page_snapshot` and `path` come from the page: untrusted, masked by the
    caller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str
    outline: list[OutlineItem]
    done: list[str] = []
    """The text of the steps already taken, in order (written by code, trusted)."""
    path: str = "/"
    page_snapshot: str = ""
    example_suffix: str | None = None
    site_notes: str | None = None
    """Notes about the site from earlier verified workflows (#480). Built from pages: untrusted."""


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    thought: str
    outline_seq: int | None
    step: PlannedStep | None
    """None: the agent says the task is done."""
    model: str
    llm_attempts: list[LLMAttempt]


class OutlinePlanner:
    """Task → a step-mode `Plan`: the outline, no steps."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def plan(self, request: PlanRequest) -> PlanResult:
        prompt = build_prompt(
            request.task,
            start_path=request.start_path,
            page_snapshot=request.page_snapshot,
            site=request.site,
            signed_in_as=request.signed_in_as,
            practice_repo=request.practice_repo,
            example_suffix=request.example_suffix,
        )
        result = await self._llm.generate(system=OUTLINE_SYSTEM, prompt=prompt, schema=LLMOutline)
        draft = result.value
        items = [t.strip() for t in draft.outline if t.strip()][:MAX_OUTLINE_ITEMS]
        if draft.clarification_question and not items:
            raise NeedsClarificationError(draft.clarification_question, result.attempts)
        if not items or not draft.expected_result.strip():
            raise PlannerError("the outline is empty", result.attempts)
        plan = Plan(
            id=uuid4(),
            task_id=request.task_id,
            revision=1,
            status="proposed",
            risk=draft.risk,
            expected_result=draft.expected_result.strip(),
            title=(draft.title or "").strip() or None,
            mode="steps",
            outline=[OutlineItem(seq=i, text=t) for i, t in enumerate(items, start=1)],
            steps=[],
            created_at=datetime.now(UTC),
        )
        return PlanResult(plan=plan, model=result.model, llm_attempts=result.attempts)


class StepDecider:
    """The page right now → the next action (as a `PlannedStep` with an empty expected state), or done."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def decide(self, ctx: StepContext, *, seq: int) -> Decision:
        result = await self._llm.generate(system=DECIDE_SYSTEM, prompt=decide_prompt(ctx), schema=LLMDecision)
        raw = result.value
        step = to_step(raw, seq)
        return Decision(
            thought=neutralize_tags(raw.thought.strip())[:300],
            outline_seq=raw.outline_seq,
            step=step,
            model=result.model,
            llm_attempts=result.attempts,
        )


def decide_prompt(ctx: StepContext) -> str:
    outline = "\n".join(f"{o.seq}. {o.text}" for o in ctx.outline)
    done = "\n".join(f"{i}. {t}" for i, t in enumerate(ctx.done, start=1)) or "(none yet)"
    parts = [f"Task: {ctx.task}", f"Outline:\n{outline}", f"Steps done so far:\n{done}"]
    if ctx.example_suffix:
        parts.append(f"Example suffix (end the example names you make up with it): {ctx.example_suffix}")
    parts.append(f"Current URL path: {neutralize_tags(ctx.path)}")
    if ctx.site_notes:
        parts.append(untrusted_block("site_notes", ctx.site_notes))
    parts.append(untrusted_block("page_snapshot", redact_snapshot(ctx.page_snapshot)))
    return "\n\n".join(parts)


_CLICKABLE = re.compile(r"^(button|link|checkbox|radio|switch|tab|menuitem\w*|option|treeitem)$")


def normalize(raw: LLMDecision) -> LLMDecision:
    """Fix the verb slips a model makes while picking the right element (spike #457: qwen2.5 chose `press`
    or `check` on a button or link in 5 of 11 cases; Gemini once pressed Enter without a target)."""
    role = raw.target.role if raw.target else ""
    action, value = raw.action, raw.value
    if action == "check" or (action == "press" and _CLICKABLE.match(role)):
        action, value = "click", None
    elif action == "press" and not (value or "").strip():
        value = "Enter"
    elif action == "fill" and _CLICKABLE.match(role) and role not in ("option",):
        action, value = "click", None
    return raw.model_copy(update={"action": action, "value": value})


def to_step(raw: LLMDecision, seq: int) -> PlannedStep | None:
    """The decision (after `normalize`) as a step to run, or None for done. The expected state stays empty:
    the executor fills it from what the action changed. The policy and the locator see exactly what was
    chosen."""
    raw = normalize(raw)
    if raw.action == "done":
        return None
    target = Target(role=raw.target.role, name=raw.target.name) if raw.target else Target()
    action = Action(type=raw.action, value=raw.value)
    text = tutorial_text(action, target if raw.target else None, None, page_title=None, sensitive=False)
    return PlannedStep(
        seq=seq,
        action=action,
        target=target,
        instruction_text=text or _fallback_text(raw),
        expected_state=ExpectedState(),
        risk=raw.risk,
    )


def _fallback_text(raw: LLMDecision) -> str:
    match raw.action:
        case "navigate":
            return f"Go to {raw.value or 'the page'}."
        case "wait":
            return "Wait for the page."
        case "press":
            return f"Press “{raw.value or 'Enter'}”."
    return raw.thought.strip()[:120] or "Continue."

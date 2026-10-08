from collections.abc import Callable

from app.agent.runlog import MASK, looks_sensitive
from app.contracts_gen.plan_schema import Plan
from app.runs.runner import Approve

type Ask = Callable[[str], str]


def format_plan(plan: Plan) -> str:
    lines = [f"Plan ({len(plan.steps)} steps, risk {plan.risk}): {plan.expected_result}"]
    for s in plan.steps:
        target = f'{s.target.role or ""} "{s.target.name or s.target.selector or ""}"'.strip()
        shown = MASK if looks_sensitive(s.target.name) else s.action.value
        value = f" = {shown!r}" if s.action.value is not None else ""
        lines.append(f"  {s.seq}. [{s.risk}] {s.instruction_text}  ({s.action.type} {target}{value})")
    return "\n".join(lines)


def console_approver(*, auto_approve: bool, ask: Ask = input, show: Callable[[str], None] = print) -> Approve:
    """Plan → approve → execute. `--yes` approves low/medium plans; a high-risk step (delete, transfer,
    publish, send, pay, security changes; AGENTS.md §4) always needs a typed "yes"."""

    async def approve(plan: Plan) -> bool:
        show(format_plan(plan))
        high = [s.seq for s in plan.steps if s.risk == "high"]
        if auto_approve and not high:
            show("Approved (--yes).")
            return True
        if high:
            answer = ask(f"Steps {high} are HIGH risk. Type 'yes' to run this plan: ")
            return answer.strip().lower() == "yes"
        return ask("Run this plan? [y/N] ").strip().lower() in ("y", "yes")

    return approve

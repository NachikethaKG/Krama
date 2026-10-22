"""The last check of a run (#274): did the verified steps do the WHOLE task, or did the plan leave part out?

Every step can verify while the run still misses what was asked (the plan created the branch but never
added the file). One LLM call compares the task with the steps that ran and the final page. It is
conservative: only a clear "not done" fails the run; an unsure answer or an LLM error keeps the run verified
(quota must never fail a run that did its work).
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.llm import UNTRUSTED_DATA_RULE, LLMAttempt, LLMError, LLMProvider, untrusted_block

SYSTEM_PROMPT = "\n".join(
    [
        "You check whether a finished browser automation did the WHOLE task the user asked for.",
        "You get the task, the steps that ran (each one was already verified to have worked) and the page",
        "the run ended on.",
        "- done=true if every part of the task is covered by the steps.",
        "- done=false only if a part of the task was clearly NOT done by any step (e.g. the task asks for",
        "  two things and the steps only do one). Name that part in missing, in a few words.",
        "- done=null if you can't tell.",
        "Wording differences are fine: judge what was done, not how the steps are phrased.",
        "",
        UNTRUSTED_DATA_RULE,
    ]
)


class TaskAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    done: bool | None
    missing: str
    """The part of the task that wasn't done; empty when done."""


class TaskVerdict(BaseModel):
    done: bool | None
    missing: str = ""
    attempts: list[LLMAttempt] = []


class TaskChecker(Protocol):
    async def check(self, task: str, steps: Sequence[str], final_path: str, final_page: str) -> TaskVerdict:
        """`final_path` and `final_page` (ARIA snapshot) come from the page: mask secrets before calling."""
        ...


class GeminiTaskChecker:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def check(self, task: str, steps: Sequence[str], final_path: str, final_page: str) -> TaskVerdict:
        try:
            prompt = build_prompt(task, steps, final_path, final_page)
            result = await self._llm.generate(system=SYSTEM_PROMPT, prompt=prompt, schema=TaskAnswer)
        except LLMError as e:
            return TaskVerdict(done=None, missing="task check unavailable", attempts=e.attempts)
        answer = result.value
        missing = "" if answer.done else answer.missing.strip()[:300]
        return TaskVerdict(done=answer.done, missing=missing, attempts=result.attempts)


def build_prompt(task: str, steps: Sequence[str], final_path: str, final_page: str) -> str:
    """The task comes from the user and the steps from the approved plan; the page parts are untrusted."""
    lines = [f"Task: {task}", "", "Steps that ran, all verified:"]
    lines += [f"{i}. {text}" for i, text in enumerate(steps, start=1)]
    lines += [
        "",
        "The run ended on this page:",
        untrusted_block("final_url_path", final_path),
        untrusted_block("final_page", final_page),
        "",
        "Was the whole task done? Reply with done and missing.",
    ]
    return "\n".join(lines)

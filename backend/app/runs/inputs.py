"""\"Do it for me\" inputs (#129, #400): the values of a stored workflow the user chooses, and the plan.

A recorded run typed example values (a repository name). The same value then reappears in later steps: URL
checks (`^/demo/demo-repo$`), titles, headings, link names and the step text. So an input is not one `fill`:
the user's value replaces the example in every step field where it appears as a whole token (decisions
P2-P5, P12, P15 in docs/research/phase-6-decisions-alignment.md).

Pure functions on stored steps; the API and the run live in #401.
"""

import re
import string
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.agent.runlog import MASK
from app.contracts_gen.workflow_schema import WorkflowInput
from app.db import WorkflowStepRow
from app.planner.instructions import field_noun
from app.runs.reverify import plan_steps

MIN_LENGTH = 3
"""Shortest value a user may type (P5); shorter ones match too much of a page's text."""

_MAX_WORDS = 8
"""Longer text is a body, not a name: the tutorial text doesn't treat it as an example either."""

_WORD = r"A-Za-z0-9"
"""A value counts only as a whole token: not next to a letter or digit ("main" in "maintenance" isn't one)."""


class DoItRefusedError(Exception):
    """The workflow can't be run for the user. `reason` goes in the 409's details (docs/api-contract.md)."""

    def __init__(self, reason: str, message: str, step_seq: int | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.step_seq = step_seq


class InputUnsafeError(ValueError):
    """A value the user sent can't be used (422 `input_unsafe`). `key` names the input."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key


def check_eligible(status: str, steps: Sequence[WorkflowStepRow], *, pending_review: bool) -> None:
    """Raise DoItRefusedError unless the workflow may run for its owner (P2, P12).

    High-risk steps are allowed: someone is watching a do-it run, so they pause for confirmation."""
    if status != "verified":
        raise DoItRefusedError("not_verified", "Only a verified workflow can run for you")
    if pending_review:
        raise DoItRefusedError("pending_review", "A new version of this workflow waits for your review")
    if not steps:
        raise DoItRefusedError("not_verified", "The workflow has no steps")
    for step in steps:
        if step.sensitive or (step.action or {}).get("value") == MASK:
            message = f"Step {step.seq} typed a secret, and secrets are never stored"
            raise DoItRefusedError("secret_not_stored", message, step.seq)


@dataclass(frozen=True)
class _Candidate:
    value: str
    label: str | None
    seq: int


def find_inputs(steps: Sequence[WorkflowStepRow]) -> list[WorkflowInput]:
    """The values the user chooses: every non-sensitive, single-line `fill` (P3), one per distinct value.

    Dropdowns (`select`) replay the recorded option (P15). The recorded value is the example, never a
    default."""
    ordered = sorted(steps, key=lambda s: s.seq)
    candidates: dict[str, _Candidate] = {}
    for step in ordered:
        action = step.action or {}
        value = action.get("value")
        if action.get("type") != "fill" or step.sensitive or not isinstance(value, str) or value == MASK:
            continue
        if not value.strip() or "\n" in value or len(value.split()) > _MAX_WORDS:
            continue
        candidates.setdefault(value, _Candidate(value, (step.target or {}).get("name"), step.seq))
    planned = plan_steps(ordered)
    keys: set[str] = set()
    inputs = []
    for c in candidates.values():
        noun = field_noun(c.label) if c.label else ""
        key = _unique_key(_key(noun) or f"step_{c.seq}_value", keys)
        inputs.append(
            WorkflowInput(
                key=key,
                label=noun[:1].upper() + noun[1:] if noun else f"Value for step {c.seq}",
                example=c.value,
                kind="text",
                pattern=_pattern(c.value),
                min_length=min(MIN_LENGTH, len(c.value)),
                steps=[p["seq"] for p in planned if _mentions(p, c.value)],
            )
        )
    return inputs


def check_values(inputs: Sequence[WorkflowInput], values: Mapping[str, str]) -> dict[str, str]:
    """The user's values by example, or InputUnsafeError for a missing, unknown, short or odd one (P5)."""
    known = {i.key for i in inputs}
    for key in values:
        if key not in known:
            raise InputUnsafeError(key, f"Unknown input {key!r}")
    by_example: dict[str, str] = {}
    for i in inputs:
        value = values.get(i.key)
        if value is None:
            raise InputUnsafeError(i.key, f"{i.label} is missing")
        if value != value.strip() or "\n" in value or "\r" in value:
            raise InputUnsafeError(i.key, f"{i.label} must be one line without leading or trailing spaces")
        if len(value) < i.min_length:
            raise InputUnsafeError(i.key, f"{i.label} needs at least {i.min_length} characters")
        if i.pattern is not None and re.fullmatch(i.pattern, value) is None:
            message = f"{i.label} may only use the same kind of characters as the example"
            raise InputUnsafeError(i.key, message)
        by_example[i.example] = value
    return by_example


def substitute(planned: Iterable[dict[str, Any]], replacements: Mapping[str, str]) -> list[dict[str, Any]]:
    """The planned steps with every example replaced by the user's value (P4).

    Every string in a step's action, target, step text and expected state is rewritten in one pass (so one
    value can't turn into another input's example). In `url_matches`, a regex, the example is found escaped or
    not and the new value goes in escaped."""
    swaps = {old: new for old, new in replacements.items() if old != new}
    if not swaps:
        return [dict(p) for p in planned]
    text = _token_regex(swaps)
    regex = re.compile(
        "|".join(f"(?<![{_WORD}])({_regex_spelling(old)})(?![{_WORD}])" for old in _longest_first(swaps))
    )
    olds = _longest_first(swaps)

    def plain(s: str) -> str:
        return text.sub(lambda m: swaps[m.group(0)], s)

    def in_regex(s: str) -> str:
        return regex.sub(lambda m: re.escape(swaps[olds[m.lastindex - 1]]), s)  # type: ignore[operator]

    out = []
    for step in planned:
        new = {k: _walk(v, plain) for k, v in step.items()}
        url = (step.get("expected_state") or {}).get("url_matches")
        if isinstance(url, str):
            new["expected_state"]["url_matches"] = in_regex(url)
        out.append(new)
    return out


def do_it_steps(steps: Sequence[WorkflowStepRow], values: Mapping[str, str]) -> list[dict[str, Any]]:
    """The plan a do-it run executes: the stored steps with the user's checked values in place."""
    ordered = sorted(steps, key=lambda s: s.seq)
    return substitute(plan_steps(ordered), check_values(find_inputs(ordered), values))


# --- helpers


def _key(noun: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", noun.lower()).strip("_")
    return key if key[:1].isalpha() else ""


def _unique_key(key: str, taken: set[str]) -> str:
    n, unique = 2, key
    while unique in taken:
        unique, n = f"{key}_{n}", n + 1
    taken.add(unique)
    return unique


_NAME_CHARS = "._-"
"""Safe in any name or slug (repository, branch, label), so always allowed for a name-like value."""


def _pattern(example: str) -> str | None:
    """The example's character class (P5) for a name-like value (no spaces): ASCII letters, digits, `._-` and
    any other punctuation the example used. A site may rename other characters (spaces in a repository name),
    which would fail a later step after something was already created. Free text with spaces, or with letters
    outside ASCII, accepts any single line; the length rule still applies."""
    if any(c.isspace() for c in example):
        return None
    others = sorted({c for c in example if not (c.isascii() and c.isalnum())} - set(_NAME_CHARS))
    if any(c not in string.punctuation for c in others):
        return None
    return "^[A-Za-z0-9" + "".join(re.escape(c) for c in others) + "._-]+$"


def _longest_first(swaps: Mapping[str, str]) -> list[str]:
    return sorted(swaps, key=len, reverse=True)


def _token_regex(swaps: Mapping[str, str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(old) for old in _longest_first(swaps))
    return re.compile(f"(?<![{_WORD}])(?:{alternatives})(?![{_WORD}])")


def _regex_spelling(old: str) -> str:
    """A regex that finds `old` inside another regex, whether each character was escaped there or not."""
    return "".join(f"\\\\?{re.escape(c)}" if not c.isalnum() else re.escape(c) for c in old)


def _walk(value: Any, fn: Any) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_walk(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _walk(v, fn) for k, v in value.items()}
    return value


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)


def _mentions(step: Mapping[str, Any], value: str) -> bool:
    """Whether the planned step carries `value` anywhere `substitute` would replace it."""
    found = _token_regex({value: value})
    spelled = re.compile(f"(?<![{_WORD}]){_regex_spelling(value)}(?![{_WORD}])")
    url = (step.get("expected_state") or {}).get("url_matches")
    if isinstance(url, str) and spelled.search(url):
        return True
    return any(found.search(s) for s in _strings(dict(step)))

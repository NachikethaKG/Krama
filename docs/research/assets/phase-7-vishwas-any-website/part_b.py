"""Phase 7 spike (#457), Part B: Gemini vs a local model on the per-step decisions of a look-before-each-step agent.

1. `capture`: open each case's page with Playwright, bring it to the case's state, save the ARIA snapshot
   (the same `page_snapshot` the planner gets) to cases.json.
2. `ask <provider> <model>`: ask every case's question through Krama's own `LLMProvider` and grade the reply
   against the hand-written answer. Providers: gemini (model chain from settings) or ollama:<model>.

Questions: "next" = what is the single next action toward the task; "done" = is the task finished on this page.
Run from backend/:  uv run python <path>/part_b.py capture <dir>  |  ask <dir> <label> <provider> [case ...]
"""

import asyncio
import json
import re
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

from playwright.async_api import Page, async_playwright
from pydantic import BaseModel, ConfigDict, Field

from app.agent import page_snapshot
from app.config import get_settings
from app.llm import (
    DEFAULT_MODELS,
    UNTRUSTED_DATA_RULE,
    GeminiProvider,
    LLMError,
    LLMProvider,
    OllamaProvider,
    untrusted_block,
)

type Setup = Callable[[Page], Awaitable[None]]

CAP = 48_000
"""Characters of the body snapshot sent to every model (~12k tokens: fits a 16k local context)."""


async def nothing(page: Page) -> None:
    pass


def typed(role: str, name: str, value: str) -> Setup:
    async def go(page: Page) -> None:
        await page.get_by_role(role, name=name).first.fill(value)  # type: ignore[arg-type]

    return go


def todo(*items: str, complete: bool = False) -> Setup:
    async def go(page: Page) -> None:
        box = page.get_by_role("textbox", name="What needs to be done?")
        for item in items:
            await box.fill(item)
            await box.press("Enter")
        if complete:
            await page.get_by_role("checkbox", name="Toggle Todo").first.check()

    return go


WIKI_TASK = "Search Wikipedia for Alan Turing and open his article"
OSM_TASK = "Search the map for Bengaluru"
TODO_TASK = "Add a todo called Buy milk and mark it as completed"
PY_TASK = "Search the Python documentation for asyncio.gather and open its entry"
MDN_TASK = "Find the MDN reference page for the JavaScript Array.prototype.map method"
GH_TASK = "Find the open issues of the microsoft/playwright repository that are labelled 'documentation'"

# Each case: page + state, task, the steps already done, the question, and what counts as right.
# next: acceptable answers as (action types, role regex, name regex, value regex or None).
# done: the right yes/no.
CASES: list[dict[str, Any]] = [
    {"id": "wiki-home-next", "url": "https://en.wikipedia.org/wiki/Main_Page", "task": WIKI_TASK, "done_steps": [],
     "q": "next", "ok": [(["fill", "click"], "searchbox|combobox|textbox", "search", r"alan turing|^$|None")]},
    {"id": "wiki-typed-next", "url": "https://en.wikipedia.org/wiki/Main_Page", "setup": "wiki_typed",
     "task": WIKI_TASK, "done_steps": ["Typed Alan Turing in the search box"],
     "q": "next", "ok": [(["click", "press"], "button|searchbox|combobox|textbox|option", "search|alan turing", None)]},
    {"id": "wiki-article-done", "url": "https://en.wikipedia.org/wiki/Alan_Turing", "task": WIKI_TASK,
     "done_steps": ["Typed Alan Turing in the search box", "Pressed Enter"], "q": "done", "ok": True},
    {"id": "wiki-home-done", "url": "https://en.wikipedia.org/wiki/Main_Page", "task": WIKI_TASK,
     "done_steps": [], "q": "done", "ok": False},
    {"id": "osm-home-next", "url": "https://www.openstreetmap.org/", "task": OSM_TASK, "done_steps": [],
     "q": "next", "ok": [(["fill"], "textbox|searchbox|combobox", "search", "bengaluru")]},
    {"id": "osm-typed-next", "url": "https://www.openstreetmap.org/", "setup": "osm_typed", "task": OSM_TASK,
     "done_steps": ["Typed Bengaluru in the Search box"], "q": "next",
     "ok": [(["click"], "button", "^go$|search", None), (["press"], "textbox|searchbox", "search", "enter")]},
    {"id": "osm-results-done", "url": "https://www.openstreetmap.org/search?query=Bengaluru", "task": OSM_TASK,
     "done_steps": ["Typed Bengaluru in the Search box", "Clicked Go"], "q": "done", "ok": True},
    {"id": "todo-empty-next", "url": "https://demo.playwright.dev/todomvc/", "task": TODO_TASK, "done_steps": [],
     "q": "next", "ok": [(["fill"], "textbox", "what needs to be done", "buy milk")]},
    {"id": "todo-typed-next", "url": "https://demo.playwright.dev/todomvc/", "setup": "todo_typed",
     "task": TODO_TASK, "done_steps": ["Typed Buy milk in the What needs to be done? box"], "q": "next",
     "ok": [(["press"], "textbox", "what needs to be done", "enter")]},
    {"id": "todo-added-next", "url": "https://demo.playwright.dev/todomvc/", "setup": "todo_added",
     "task": TODO_TASK, "done_steps": ["Typed Buy milk in the What needs to be done? box", "Pressed Enter"],
     "q": "next", "ok": [(["click", "check"], "checkbox", "toggle todo|buy milk", None)]},
    {"id": "todo-added-done", "url": "https://demo.playwright.dev/todomvc/", "setup": "todo_added",
     "task": TODO_TASK, "done_steps": ["Typed Buy milk in the What needs to be done? box", "Pressed Enter"],
     "q": "done", "ok": False},
    {"id": "todo-completed-done", "url": "https://demo.playwright.dev/todomvc/", "setup": "todo_completed",
     "task": TODO_TASK, "done_steps": ["Added Buy milk", "Ticked its checkbox"], "q": "done", "ok": True},
    {"id": "todo-other-done", "url": "https://demo.playwright.dev/todomvc/", "setup": "todo_other",
     "task": TODO_TASK, "done_steps": ["Added a todo", "Ticked its checkbox"], "q": "done", "ok": False},
    {"id": "py-home-next", "url": "https://docs.python.org/3/", "task": PY_TASK, "done_steps": [], "q": "next",
     "ok": [(["fill"], "searchbox|textbox|combobox", "search", "asyncio")]},
    {"id": "py-results-next", "url": "https://docs.python.org/3/search.html?q=asyncio.gather", "task": PY_TASK,
     "done_steps": ["Searched for asyncio.gather"], "q": "next",
     "ok": [(["click"], "link", "asyncio\\.gather|gather", None)]},
    {"id": "py-results-done", "url": "https://docs.python.org/3/search.html?q=asyncio.gather", "task": PY_TASK,
     "done_steps": ["Searched for asyncio.gather"], "q": "done", "ok": False},
    {"id": "mdn-home-next", "url": "https://developer.mozilla.org/en-US/", "task": MDN_TASK, "done_steps": [],
     "q": "next", "ok": [(["fill"], "searchbox|textbox|combobox", "search", "map"),
                         (["click"], "button|link", "search|references|javascript", None)]},
    {"id": "gh-issues-next", "url": "https://github.com/microsoft/playwright/issues", "task": GH_TASK,
     "done_steps": ["Opened the repository's Issues tab"], "q": "next",
     "ok": [(["click"], "button|link", "label", None),
            (["fill"], "textbox|searchbox|combobox", "search|filter", "label:.?documentation")]},
]

SETUPS: dict[str, Setup] = {
    "wiki_typed": typed("searchbox", "Search Wikipedia", "Alan Turing"),
    "osm_typed": typed("textbox", "Search", "Bengaluru"),
    "todo_typed": typed("textbox", "What needs to be done?", "Buy milk"),
    "todo_added": todo("Buy milk"),
    "todo_completed": todo("Buy milk", complete=True),
    "todo_other": todo("Walk the dog", complete=True),
}


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(description="ARIA role of the element, from the snapshot")
    name: str = Field(description="its accessible name, exactly as in the snapshot")


class NextAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thought: str = Field(description="one short sentence: what the page shows and what is left to do")
    action: Literal["click", "fill", "press", "select", "check", "navigate", "done"]
    target: Target | None = Field(description="the element to act on; null for navigate and done")
    value: str | None = Field(description="text to type, key to press (e.g. Enter), option, or URL path")


class DoneCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: str = Field(description="one short sentence: what on the page shows it")
    done: bool


SYSTEM_NEXT = f"""You operate a web browser for a user, one step at a time.
You get the user's task, the steps already done, and the current page as an ARIA snapshot.
Decide the single next action toward the task. Use only elements that are in the snapshot, with their exact
role and accessible name. Use "fill" to type into a field, "press" with a key name for keys (e.g. Enter),
"check" for checkboxes. If the task is already complete, answer "done".
{UNTRUSTED_DATA_RULE}"""

SYSTEM_DONE = f"""You check a web browser task for a user.
You get the user's task, the steps already done, and the current page as an ARIA snapshot.
Say whether the WHOLE task is complete on this page. Only what the page shows counts.
{UNTRUSTED_DATA_RULE}"""


def prompt_for(case: dict[str, Any], snapshot: str, url: str) -> str:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(case["done_steps"], 1)) or "(none yet)"
    return "\n\n".join(
        [f"Task: {case['task']}", f"Steps done so far:\n{steps}", f"Current URL: {url}",
         untrusted_block("page_snapshot", snapshot)]
    )


def grade(case: dict[str, Any], reply: BaseModel) -> bool:
    if case["q"] == "done":
        return isinstance(reply, DoneCheck) and reply.done is case["ok"]
    assert isinstance(reply, NextAction)
    for types, role, name, value in case["ok"]:
        if reply.action not in types or reply.target is None:
            continue
        if not re.search(role, reply.target.role, re.I) or not re.search(name, reply.target.name, re.I):
            continue
        if value is not None and not re.search(value, str(reply.value), re.I):
            continue
        return True
    return False


async def capture(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for case in CASES:
            page = await browser.new_page(viewport={"width": 1280, "height": 800}, locale="en-US")
            try:
                await page.goto(case["url"], wait_until="domcontentloaded", timeout=45_000)
                await page.wait_for_timeout(2500)
                await SETUPS.get(case.get("setup", ""), nothing)(page)
                await page.wait_for_timeout(800)
                main = await page_snapshot(page)  # what the planner gets today: <main> only, if there is one
                body = await page.locator("body").aria_snapshot(timeout=10_000)
                snap = body[:CAP]
                cases.append({**case, "snapshot": snap, "page_url": page.url,
                              "main_chars": len(main), "body_chars": len(body), "capped": len(body) > CAP})
                print(f"{case['id']}: main {len(main)}, body {len(body)} chars")
            except Exception as e:  # a site that blocks or times out is a finding, not a crash
                print(f"{case['id']}: FAILED {type(e).__name__}: {str(e)[:200]}")
            finally:
                await page.close()
        await browser.close()
    (out / "cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False), encoding="utf-8")


def provider_for(spec: str) -> LLMProvider:
    settings = get_settings()
    if spec == "gemini":
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model_list or DEFAULT_MODELS)
    model = spec.split(":", 1)[1]
    return OllamaProvider(settings.ollama_url, model, timeout_s=600, num_ctx=16384)


async def ask(out: Path, label: str, spec: str, only: list[str]) -> None:
    cases = json.loads((out / "cases.json").read_text(encoding="utf-8"))
    llm = provider_for(spec)
    results = []
    for case in cases:
        if only and case["id"] not in only:
            continue
        schema: type[BaseModel] = NextAction if case["q"] == "next" else DoneCheck
        system = SYSTEM_NEXT if case["q"] == "next" else SYSTEM_DONE
        t0 = time.perf_counter()
        row: dict[str, Any] = {"case": case["id"], "q": case["q"], "snapshot_chars": len(case["snapshot"])}
        try:
            result = await llm.generate(
                system=system, prompt=prompt_for(case, case["snapshot"], case["page_url"]), schema=schema
            )
            row |= {
                "correct": grade(case, result.value),
                "reply": result.value.model_dump(),
                "model": result.model,
                "attempts": [a.model_dump() for a in result.attempts],
            }
        except LLMError as e:
            row |= {"correct": False, "error": str(e)[:300], "attempts": [a.model_dump() for a in e.attempts]}
        row["seconds"] = round(time.perf_counter() - t0, 1)
        results.append(row)
        print(f"{case['id']:22} {'OK ' if row['correct'] else 'BAD'} {row['seconds']:6}s "
              f"{json.dumps(row.get('reply') or row.get('error'), ensure_ascii=False)[:150]}", flush=True)
    path = out / f"answers-{label}.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() and only else []
    keep = [r for r in previous if r["case"] not in {x["case"] for x in results}]
    path.write_text(json.dumps(keep + results, indent=1, ensure_ascii=False), encoding="utf-8")
    right = sum(r["correct"] for r in keep + results)
    print(f"{label}: {right}/{len(keep + results)} correct")


if __name__ == "__main__":
    command, out = sys.argv[1], Path(sys.argv[2])
    if command == "capture":
        asyncio.run(capture(out))
    else:
        asyncio.run(ask(out, sys.argv[3], sys.argv[4], sys.argv[5:]))

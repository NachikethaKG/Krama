"""Instruction-text rewrite: template (no LLM) vs Gemini vs local Ollama models, on the same real steps.

One LLM call per workflow (all its steps at once). Step data comes from the page, so it is passed as an
untrusted block; the rules live in the system prompt. Every output is scored with the automatic checks below.
Run from backend/:  uv run python ../docs/research/assets/phase-2-vishwas-instruction-text/instruct.py <provider>...
  providers: template | gemini:<model> | ollama:<model> | ollama-cpu:<model> (GPU off)
"""
import asyncio, json, re, sys, time, urllib.request
from collections import defaultdict
from pathlib import Path
from pydantic import BaseModel
from app.config import get_settings
from app.llm.gemini import GeminiProvider
from app.llm.untrusted import UNTRUSTED_DATA_RULE, untrusted_block

HERE = Path(__file__).parent


class Line(BaseModel):
    seq: int
    text: str


class Rewritten(BaseModel):
    steps: list[Line]


SYSTEM = "\n".join([
    "You write the step text of an interactive software tutorial. Each step is shown next to a highlight of the",
    "element on the real page, so the text must say exactly what to do, in the words a careful technical writer",
    "would use (Microsoft and Google style guides).",
    "",
    "Rules for every step:",
    "- One short sentence, at most 20 words, ending with a period. Start with an imperative verb.",
    "- If the element is inside a dialog, a menu or a named section, say where FIRST:",
    '  "In the **Create new branch** dialog, click **Confirm**." / "Under **Basic Settings**, ..."',
    "- Put the element's visible label in bold, copied character for character from `label`.",
    "- Verbs: click for buttons, links and menu items; select for checkboxes and radio buttons",
    '  ("Select the **Private** checkbox."); enter for text fields ("Enter `my-repo` in **Repository Name**.").',
    "- Put typed values in backticks, exactly as given. If the value has several lines, write",
    '  "Enter the file content in **<label>**." without the value.',
    "- For a navigate step, name the page you arrive on (from `arrives_on`), not the URL:",
    '  "Go to the **Branches** page of the repository."',
    "- Never use above, below, left, right or please. Never mention elements, labels or values that are not",
    "  in the data. Don't explain why; the tutorial shows the result.",
    "- Return one entry per input step, with the same seq.",
    "",
    'Example input step: {"seq": 1, "action": "click", "role": "menuitem", "label": "Your Profile", "inside": "top bar menu"}',
    'Example output: {"seq": 1, "text": "In the top bar menu, click **Your Profile**."}',
    "",
    UNTRUSTED_DATA_RULE,
])


def clean(label: str | None) -> str | None:
    return label.removesuffix(" *").strip() if label else label


def task_steps(rows: list[dict]) -> dict[str, list[dict]]:
    by = defaultdict(list)
    for r in rows:
        by[r["task"]].append(r)
    out = {}
    for task, rs in by.items():
        items = []
        for i, r in enumerate(rs):
            nxt = rs[i + 1] if i + 1 < len(rs) else None
            it = {"seq": i + 1, "action": r["action"]}
            if r.get("name"):
                role = r.get("real_role") if r.get("real_role") in ("menu", "menuitem") else r["role"]
                it |= {"role": role, "label": clean(r["name"])}
            if r.get("value") is not None:
                it["value"] = r["value"]
            if r.get("container"):
                it["inside"] = r["container"]
            elif r.get("section_heading") and r["section_heading"] not in r["page_title"]:
                it["section"] = r["section_heading"]
            if r["action"] == "navigate" and nxt:
                it["arrives_on"] = nxt["page_title"].split(" - Gitea")[0]
            items.append(it)
        out[task] = items
    return out


def template(items: list[dict]) -> list[str]:
    """Deterministic baseline: no LLM at all."""
    texts = []
    for it in items:
        where = ""
        inside = it.get("inside", "")
        if inside.startswith("dialog"):
            where = f"In the **{inside[8:-1]}** dialog, "
        elif "menu" in inside:
            where = "In the menu, "
        elif it.get("section"):
            where = f"Under **{it['section']}**, "
        lab = it.get("label")
        match it["action"]:
            case "navigate":
                t = f"Go to the **{it.get('arrives_on', it['value']).split(' - ')[0]}** page."
            case "fill" if "\n" in it["value"]:
                t = f"enter the file content in **{lab}**."
            case "fill":
                t = f"enter `{it['value']}` in **{lab}**."
            case "click" if it.get("role") in ("checkbox", "radio"):
                t = f"select the **{lab}** checkbox."
            case _:
                t = f"click **{lab}**."
        t = where + t
        texts.append(t[0].upper() + t[1:])
    return texts


class Ollama:
    """Same shape as LLMProvider.generate: JSON-schema constrained output via Ollama's /api/chat `format`."""

    def __init__(self, model: str, *, cpu_only: bool = False) -> None:
        self.model = model
        self.cpu_only = cpu_only  # num_gpu 0: what a laptop without a GPU gets

    async def generate(self, *, system: str, prompt: str, schema: type[BaseModel]):
        body = {"model": self.model, "stream": False, "format": schema.model_json_schema(),
                "options": {"temperature": 0, **({"num_gpu": 0} if self.cpu_only else {})},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        raw = await asyncio.to_thread(lambda: json.loads(urllib.request.urlopen(req, timeout=600).read()))
        return schema.model_validate_json(raw["message"]["content"]), raw


VERBS = {"click", "select", "enter", "go", "open", "type", "clear", "choose", "check", "press"}
DIRECTIONS = re.compile(r"\b(above|below|left|right|please)\b", re.I)


def score(it: dict, text: str) -> dict[str, bool]:
    lead = text.split(", ", 1)[1] if re.match(r"^(In|Under|On)\b[^,]*,", text) else text
    bold = re.findall(r"\*\*(.+?)\*\*", text)
    inside = it.get("inside") or ""
    allowed = {it.get("label"), it.get("section"), inside[8:-1] or None, it.get("arrives_on")}
    multiline = "\n" in (it.get("value") or "")
    return {
        "imperative": lead.split(" ", 1)[0].lower().strip("*") in VERBS,
        "label_exact": it.get("label") is None or f"**{it['label']}**" in text,
        "value_exact": it["action"] != "fill" or multiline or f"`{it['value']}`" in text,
        "no_leak_multiline": not multiline or it["value"].splitlines()[-1] not in text,
        "where_first": not inside.startswith("dialog") or text.startswith("In the **"),
        "short": len(text.split()) <= 20,
        "no_direction_words": not DIRECTIONS.search(text),
        "no_invented_bold": it["action"] == "navigate" or all(b in allowed or b == it.get("value") for b in bold),
    }


async def run(provider: str, tasks: dict[str, list[dict]]) -> dict:
    res: dict = {"provider": provider, "tasks": {}}
    for task, items in tasks.items():
        t0 = time.perf_counter()
        err, model_used = None, None
        if provider == "template":
            texts = template(items)
        else:
            prompt = f"Task the tutorial teaches: {task.replace('-', ' ')}\n\n" + untrusted_block(
                "steps", "\n".join(json.dumps(i, ensure_ascii=False) for i in items))
            kind, model = provider.split(":", 1)
            try:
                if kind in ("ollama", "ollama-cpu"):
                    parsed, _raw = await Ollama(model, cpu_only=kind == "ollama-cpu").generate(system=SYSTEM, prompt=prompt, schema=Rewritten)
                    model_used = model
                else:
                    r = await GeminiProvider(get_settings().gemini_api_key, [model]).generate(
                        system=SYSTEM, prompt=prompt, schema=Rewritten)
                    parsed, model_used = r.value, r.model
                got = {line.seq: line.text for line in parsed.steps}
                texts = [got.get(i["seq"], "") for i in items]
            except Exception as e:  # noqa: BLE001 - recorded as a result
                err, texts = f"{type(e).__name__}: {str(e)[:200]}", ["" for _ in items]
        res["tasks"][task] = {"seconds": round(time.perf_counter() - t0, 1), "error": err, "model": model_used,
                              "steps": [{"in": i, "text": t, "checks": score(i, t)} for i, t in zip(items, texts)]}
    allc = [s["checks"] for t in res["tasks"].values() for s in t["steps"]]
    res["summary"] = {k: sum(c[k] for c in allc) for k in allc[0]} | {
        "all_pass": sum(all(c.values()) for c in allc), "steps": len(allc),
        "seconds_total": round(sum(t["seconds"] for t in res["tasks"].values()), 1),
        "errors": sum(1 for t in res["tasks"].values() if t["error"])}
    return res


async def main() -> None:
    tasks = task_steps(json.loads((HERE / "steps.json").read_text(encoding="utf-8")))
    (HERE / "inputs.json").write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
    for provider in sys.argv[1:]:
        res = await run(provider, tasks)
        out = HERE / f"out-{provider.replace(':', '-')}.json"
        out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(provider, json.dumps(res["summary"]))


if __name__ == "__main__":
    asyncio.run(main())

"""Part B, whole plans: send the exact first-planning prompts Gemini got in Part A to another model.

plans.py <llm-calls.jsonl> <out.json> <ollama model>   (run from backend/)
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.llm import LLMError, OllamaProvider
from app.planner.planner import LLMPlan
from app.planner.prompt import SYSTEM_PROMPT


async def main() -> None:
    log, out, model = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    # First plans only: a replan or a retry after feedback carries extra sections.
    firsts = [
        e for e in entries
        if e["schema"] == "LLMPlan" and "RE-PLANNING" not in e["prompt"] and "previous plan was rejected" not in e["prompt"]
    ]
    llm = OllamaProvider(get_settings().ollama_url, model, timeout_s=900, num_ctx=16384)
    rows = []
    for e in firsts:
        task = e["prompt"].splitlines()[0]
        t0 = time.perf_counter()
        try:
            r = await llm.generate(system=SYSTEM_PROMPT, prompt=e["prompt"], schema=LLMPlan)
            reply = r.value.model_dump(mode="json")
        except LLMError as err:
            reply = {"error": str(err)}
        rows.append({"task": task, "prompt_chars": e["prompt_chars"], "gemini": e.get("reply"), model: reply,
                     "seconds": round(time.perf_counter() - t0, 1)})
        print(f"\n## {task} ({rows[-1]['seconds']} s)")
        for who, plan in (("gemini", e.get("reply")), (model, reply)):
            print(f"  {who}:", plan.get("error") or plan.get("question") or "")
            for st in (plan or {}).get("steps", []):
                a, t = st["action"], st.get("target") or {}
                exp = {k: v for k, v in (st.get("expected_state") or {}).items() if v}
                print(f"    {a['type']} {t.get('role')} {t.get('name')!r} {a.get('value')!r} -> {json.dumps(exp)[:160]}")
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


asyncio.run(main())

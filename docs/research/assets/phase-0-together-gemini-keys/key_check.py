"""#27: one structured-output call per person's key, to confirm the key works and see its quota.

Usage (from backend/):  uv run python <this> <who> <key-file> [model]
The key file holds only the key. The key is never printed.
"""

import json
import sys
import time
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

who, key_file = sys.argv[1], Path(sys.argv[2])
model = sys.argv[3] if len(sys.argv) > 3 else "gemini-2.5-flash"
key = key_file.read_text(encoding="utf-8").strip()


class Step(BaseModel):
    seq: int
    instruction_text: str
    url_after: str


class MiniPlan(BaseModel):
    steps: list[Step]


client = genai.Client(api_key=key)
t0 = time.perf_counter()
out: dict = {"who": who, "model": model, "key_len": len(key)}
try:
    r = client.models.generate_content(
        model=model,
        contents="Plan the clicks to create a repository called demo-repo in Gitea, starting from the dashboard at /.",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=MiniPlan.model_json_schema(),
            temperature=0,
        ),
    )
    plan = MiniPlan.model_validate_json(r.text or "")
    out |= {"ok": True, "steps": len(plan.steps), "first_step": plan.steps[0].instruction_text if plan.steps else None}
    if r.usage_metadata:
        out["total_tokens"] = r.usage_metadata.total_token_count
except errors.APIError as e:
    out |= {"ok": False, "error": f"{e.code} {e.status}", "message": str(e.message)[:300]}
out["ms"] = round((time.perf_counter() - t0) * 1000)
print(json.dumps(out, indent=2))

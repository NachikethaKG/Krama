"""Summarise an LLM call log: one line per call."""

import json
import sys

for line in open(sys.argv[1], encoding="utf-8"):
    e = json.loads(line)
    print(
        e["schema"],
        "ok" if e["ok"] else "FAIL",
        e.get("model"),
        f"{e['seconds']}s",
        f"{e['prompt_chars']}ch",
        "img" if e["image"] else "",
        [(a["model"], a["status"]) for a in e["attempts"]],
        (e.get("error") or "")[:120],
    )

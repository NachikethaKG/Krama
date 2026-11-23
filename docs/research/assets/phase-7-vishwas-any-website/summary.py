"""Part B table: per model, strict score, right element (ignoring the action verb), done-check score, latency."""

import json
import re
import statistics
import sys
from pathlib import Path

d = Path(sys.argv[1])
cases = {c["id"]: c for c in json.loads((d / "cases.json").read_text(encoding="utf-8"))}


def right_element(case: dict, reply: dict) -> bool:
    t = reply.get("target") or {}
    return any(
        re.search(role, t.get("role") or "", re.I) and re.search(name, t.get("name") or "", re.I)
        for _types, role, name, _value in case["ok"]
    )


print("| Model | Next action (strict) | Right element | Done check | Median s | Max s | Cases |")
print("|---|---|---|---|---|---|---|")
for f in sorted(d.glob("answers-*.json")):
    rows = json.loads(f.read_text(encoding="utf-8"))
    nxt = [r for r in rows if r["q"] == "next"]
    done = [r for r in rows if r["q"] == "done"]
    elem = sum(right_element(cases[r["case"]], r.get("reply") or {}) for r in nxt)
    secs = [r["seconds"] for r in rows]
    print(
        f"| {f.stem.removeprefix('answers-')} | {sum(r['correct'] for r in nxt)}/{len(nxt)} | {elem}/{len(nxt)} "
        f"| {sum(r['correct'] for r in done)}/{len(done)} | {statistics.median(secs):.1f} | {max(secs):.1f} | {len(rows)} |"
    )
print()
print("| Case | chars sent | " + " | ".join(f.stem.removeprefix("answers-") for f in sorted(d.glob("answers-*.json"))) + " |")
by = {f.stem.removeprefix("answers-"): {r["case"]: r for r in json.loads(f.read_text(encoding="utf-8"))}
      for f in sorted(d.glob("answers-*.json"))}
for cid, c in cases.items():
    cells = []
    for label in by:
        r = by[label].get(cid)
        cells.append("—" if r is None else f"{'✅' if r['correct'] else '❌'} {r['seconds']:.0f}s")
    print(f"| {cid} | {len(c['snapshot'])}{' (capped)' if c.get('capped') else ''} | " + " | ".join(cells) + " |")

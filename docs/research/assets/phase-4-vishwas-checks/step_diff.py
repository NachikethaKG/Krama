"""Workflow versions on real data: what changes between two runs of the same task, how a step diff looks, and what
copy-on-write rows cost against a JSON Patch per version.

Reads the stored workflows from the local Postgres (docker exec psql, so no DB credentials in this script).
Groups them by task prompt: ~20 runs of the same benchmark task on the same, unchanged Gitea are the best stand-in
we have for "two versions with no UI drift". Then:
  1. semantic signatures: which step fields differ between runs of one task with no drift (noise vs meaning);
  2. step diff: align two step lists (difflib on step keys, then pair leftovers by similarity) and classify each
     step as same / changed (which fields) / added / removed, on real pairs and on a simulated self-heal
     (button renamed) and a simulated changed flow (extra confirm step);
  3. storage: bytes of a full copy of the step rows per version vs an RFC 6902 patch from the previous version.

Run from backend/:  uv run --with jsonpatch python ../docs/research/assets/phase-4-vishwas-checks/step_diff.py
Output: results-diff.json next to this script.
"""

import copy
import json
import re
import subprocess
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import jsonpatch

OUT = Path(__file__).with_name("results-diff.json")

SQL = """select coalesce(json_agg(w order by w.created_at), '[]') from (
  select w.id, w.title, w.target_app, w.created_at,
    (select json_agg(json_build_object('seq', s.seq, 'action', s.action, 'target', s.target,
       'instruction_text', s.instruction_text, 'expected_state', s.expected_state, 'risk', s.risk,
       'sensitive', s.sensitive, 'verification', s.verification,
       'row_bytes', pg_column_size(s.*)) order by s.seq) from workflow_steps s where s.workflow_id = w.id) as steps
  from workflows w where w.status = 'verified') w"""

# What a version is ABOUT (the "definition" a human approved / a tutorial teaches), vs evidence of one run.
DEFINITION = ("action", "target.role", "target.name", "expected_state", "risk", "instruction_text")
EVIDENCE = ("target.bbox", "target.scroll", "verification")


def load() -> list[dict]:
    out = subprocess.run(
        ["docker", "exec", "krama-postgres-1", "psql", "-U", "krama", "-d", "krama", "-At", "-c", SQL],
        capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout
    return [w for w in json.loads(out) if w["steps"]]


def norm(s: str | None) -> str:
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def get(step: dict, field: str):
    cur = step
    for part in field.split("."):
        cur = (cur or {}).get(part)
    return cur


def key(step: dict) -> tuple:
    """What the step does, ignoring wording and geometry: the alignment key."""
    t = step.get("target") or {}
    return (step["action"]["type"], t.get("role"), norm(t.get("name")), step["action"].get("value"))


def similarity(a: dict, b: dict) -> float:
    if a["action"]["type"] != b["action"]["type"]:
        return 0.0
    ta, tb = a.get("target") or {}, b.get("target") or {}
    role = 1.0 if ta.get("role") == tb.get("role") else 0.0
    name = SequenceMatcher(None, norm(ta.get("name")), norm(tb.get("name"))).ratio()
    text = SequenceMatcher(None, norm(a["instruction_text"]), norm(b["instruction_text"])).ratio()
    exp = 1.0 if a["expected_state"] == b["expected_state"] else 0.0
    return 0.3 * role + 0.3 * name + 0.2 * text + 0.2 * exp


def changed_fields(a: dict, b: dict) -> list[dict]:
    out = []
    for f in DEFINITION:
        va, vb = get(a, f), get(b, f)
        if va != vb:
            out.append({"field": f, "from": va, "to": vb})
    return out


def step_diff(old: list[dict], new: list[dict], pair_at: float = 0.6) -> list[dict]:
    """Align by step key (LCS via difflib), then inside each replaced block pair steps whose similarity is
    >= pair_at as `changed`; the rest are `removed` / `added`. Order-preserving, O(n*m) on ~5 steps."""
    sm = SequenceMatcher(None, [key(s) for s in old], [key(s) for s in new], autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for a, b in zip(old[i1:i2], new[j1:j2]):
                fields = changed_fields(a, b)
                rows.append({"kind": "changed" if fields else "same", "old_seq": a["seq"], "new_seq": b["seq"],
                             "fields": fields})
            continue
        left, right = list(old[i1:i2]), list(new[j1:j2])
        while left and right:
            score, a, b = max(((similarity(a, b), a, b) for a in left for b in right), key=lambda t: t[0])
            if score < pair_at:
                break
            rows.append({"kind": "changed", "old_seq": a["seq"], "new_seq": b["seq"], "similarity": round(score, 2),
                         "fields": changed_fields(a, b)})
            left.remove(a)
            right.remove(b)
        rows += [{"kind": "removed", "old_seq": a["seq"]} for a in left]
        rows += [{"kind": "added", "new_seq": b["seq"], "step": describe(b)} for b in right]
    return sorted(rows, key=lambda r: (r.get("new_seq") or 0, r.get("old_seq") or 0))


def describe(step: dict) -> str:
    t = step.get("target") or {}
    return f'{step["action"]["type"]} {t.get("role") or ""} "{t.get("name") or step["action"].get("value") or ""}"'


def definition(steps: list[dict]) -> list[dict]:
    """The version-defining content of the steps (what would go in a version row or a patch)."""
    out = []
    for s in steps:
        t = {k: v for k, v in (s.get("target") or {}).items() if k in ("role", "name", "selector")}
        out.append({"seq": s["seq"], "action": s["action"], "target": t, "instruction_text": s["instruction_text"],
                    "expected_state": s["expected_state"], "risk": s["risk"]})
    return out


def main() -> None:
    wfs = load()
    groups: dict[str, list[dict]] = defaultdict(list)
    for w in wfs:
        groups[w["title"]].append(w)
    result: dict = {"workflows": len(wfs), "tasks": []}
    for title, runs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(runs) < 5:
            continue
        sigs = Counter(tuple(key(s) for s in w["steps"]) for w in runs)
        field_noise: Counter = Counter()
        diffs_vs_first = Counter()
        for w in runs[1:]:
            d = step_diff(runs[0]["steps"], w["steps"])
            diffs_vs_first[tuple(sorted(Counter(r["kind"] for r in d).items()))] += 1
            for r in d:
                for f in r.get("fields", []):
                    field_noise[f["field"]] += 1
            if len(w["steps"]) == len(runs[0]["steps"]):
                for a, b in zip(runs[0]["steps"], w["steps"]):
                    for f in EVIDENCE:
                        if get(a, f) != get(b, f):
                            field_noise[f] += 1
        full_rows = [sum(s["row_bytes"] for s in w["steps"]) for w in runs]
        defs = [definition(w["steps"]) for w in runs]
        def_bytes = [len(json.dumps(d)) for d in defs]
        patch_bytes = [len(jsonpatch.make_patch(defs[i - 1], defs[i]).to_string()) for i in range(1, len(defs))]
        result["tasks"].append({
            "task": title,
            "runs": len(runs),
            "distinct_step_keys": len(sigs),
            "signatures": [{"count": c, "steps": [" ".join(str(x) for x in k if x) for k in sig]}
                           for sig, c in sigs.most_common(4)],
            "diff_kinds_vs_first_run": [{"kinds": dict(k), "runs": c} for k, c in diffs_vs_first.most_common()],
            "fields_that_differ_with_no_drift": dict(field_noise.most_common()),
            "bytes": {
                "step_rows_per_version_avg": round(sum(full_rows) / len(full_rows)),
                "definition_json_per_version_avg": round(sum(def_bytes) / len(def_bytes)),
                "json_patch_vs_previous_avg": round(sum(patch_bytes) / len(patch_bytes)),
                "json_patch_empty_count": sum(1 for b in patch_bytes if b <= 2),
            },
        })

    # Simulated versions of one real workflow: a self-heal and a changed flow.
    base = next(w for w in wfs if w["title"].startswith("Create a new public repository"))
    healed = copy.deepcopy(base["steps"])
    last = next(s for s in healed if (s.get("target") or {}).get("name") == "Create Repository")
    last["target"]["name"] = "Make repo"
    last["instruction_text"] = last["instruction_text"].replace("Create Repository", "Make repo")
    flow = copy.deepcopy(base["steps"])
    confirm = copy.deepcopy(flow[-1])
    confirm.update(seq=flow[-1]["seq"] + 1, instruction_text='In the dialog, click "Confirm".',
                   target={"role": "button", "name": "Confirm"})
    flow[-1]["expected_state"] = {"text_visible": ["Confirm"]}
    flow.append(confirm)
    result["simulated"] = {
        "workflow": base["id"],
        "self_heal_renamed_button": step_diff(base["steps"], healed),
        "self_heal_patch": json.loads(jsonpatch.make_patch(definition(base["steps"]), definition(healed)).to_string()),
        "changed_flow_extra_step": step_diff(base["steps"], flow),
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    for t in result["tasks"]:
        print(f'{t["task"][:60]:60} runs={t["runs"]:3} distinct={t["distinct_step_keys"]:2} '
              f'noise={t["fields_that_differ_with_no_drift"]} bytes={t["bytes"]}')
    for name in ("self_heal_renamed_button", "changed_flow_extra_step"):
        print(name, [(r["kind"], [f["field"] for f in r.get("fields", [])]) for r in result["simulated"][name]])


if __name__ == "__main__":
    main()

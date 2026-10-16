"""Print every step's text per provider, with the failed checks: python show.py out-*.json"""
import json, sys

for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    print(f"=== {r['provider']}: {r['summary']['all_pass']}/{r['summary']['steps']} pass all checks, "
          f"{r['summary']['seconds_total']} s, {r['summary']['errors']} errors")
    for task, t in r["tasks"].items():
        if t["error"]:
            print(f"  [{task}] ERROR {t['error']}")
        for s in t["steps"]:
            bad = [k for k, v in s["checks"].items() if not v]
            print(f"  {'  ' if not bad else 'XX'} {s['text']!r}" + (f"   <- {', '.join(bad)}" if bad else ""))

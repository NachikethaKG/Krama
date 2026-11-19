"""Follow-up on the loaded DB (run spike.py first): per-query latency, AND-then-OR fallback, a small synonym map,
prefix matching for search-as-you-type. Reloads 30 + 1000 (one user) and 20k/20 users. Writes results2.json."""

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import asyncpg

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import spike  # noqa: E402
from corpus import QUERIES  # noqa: E402

# A small, general synonym map applied to the query before FTS (not tuned per workflow).
SYNONYMS = {"repo": "repository", "repos": "repositories", "someone": "person user member", "invite": "invite add",
            "tag": "label", "private": "private visibility", "public": "public visibility", "pr": "pull request",
            "access": "access collaborator member", "remove": "remove delete", "erase": "delete"}


def expand(q):
    return " ".join(SYNONYMS.get(w, w) for w in q.lower().replace("?", " ").split())


RANKED = spike.METHODS["combined_ranked"]
AND_RANKED = RANKED.replace(spike.OR_QUERY.format(cfg="english"), "websearch_to_tsquery('english', $1)")


async def fallback(con, q):
    """AND first (precise, cheap); if it finds < 3, use the OR + trigram query."""
    rows = await con.fetch(AND_RANKED, q, spike.NOW, spike.ME)
    if len(rows) >= 3:
        return rows
    seen = {r["key"] or r["title"] for r in rows}
    more = [r for r in await con.fetch(RANKED, q, spike.NOW, spike.ME) if (r["key"] or r["title"]) not in seen]
    return list(rows) + more


async def plain(con, q):
    return await con.fetch(RANKED, q, spike.NOW, spike.ME)


VARIANTS = {
    "ranked_or": lambda con, q: plain(con, q),
    "ranked_and_then_or": lambda con, q: fallback(con, q),
    "ranked_or+synonyms": lambda con, q: plain(con, expand(q)),
    "ranked_and_then_or+synonyms": lambda con, q: fallback(con, expand(q)),
}


async def evaluate(con, label):
    out = {}
    for name, fn in VARIANTS.items():
        hits, per_q = 0, []
        for q, rel in QUERIES:
            rows = await fn(con, q)
            top = [r["key"] or r["title"] for r in rows[:3]]
            ok = any(k in rel for k in top)
            hits += ok
            ts = []
            for _ in range(15):
                t0 = time.perf_counter()
                await fn(con, q)
                ts.append((time.perf_counter() - t0) * 1000)
            per_q.append({"q": q, "hit": ok, "top3": top, "median_ms": round(statistics.median(ts), 2)})
        lat = [p["median_ms"] for p in per_q]
        out[name] = {"top3_hits": f"{hits}/{len(QUERIES)}", "median_ms": statistics.median(lat), "max_ms": max(lat),
                     "per_query": per_q}
        print(f"[{label}] {name:30s} top3 {hits}/{len(QUERIES)} median {statistics.median(lat):.2f} max {max(lat):.2f}")
        for p in per_q:
            print(f"     {'OK ' if p['hit'] else 'MISS'} {p['median_ms']:7.2f} ms  {p['q']!r:45s} {p['top3']}")
    return out


async def main():
    con = await asyncpg.connect(spike.DSN)
    res = {}
    await spike.load(con, 0)
    res["n30"] = await evaluate(con, "30")
    await spike.load(con, 1000)
    res["n1030"] = await evaluate(con, "1030")
    # prefix matching (search as you type): 'collab' -> collab:*
    res["prefix"] = [dict(r) for r in await con.fetch(
        "SELECT key, title FROM workflows WHERE user_id=1 AND search @@ to_tsquery('english','collab:*') LIMIT 5")]
    await spike.load(con, 20000, users=20)
    res["n20k"] = await evaluate(con, "20k/20u")
    # 'github' in the query: a user filter on target_app might matter; check how many rows OR-match 'add'
    res["or_match_counts_20k"] = {q: await con.fetchval(
        f"SELECT count(*) FROM workflows, {spike.OR_QUERY.format(cfg='english')} q WHERE $2::int=$2 AND user_id=1 AND search @@ q", q, 1)
        for q, _ in QUERIES}
    await con.close()
    (HERE / "results2.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")


asyncio.run(main())

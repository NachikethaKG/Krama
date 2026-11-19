"""#135 search spike: Postgres FTS vs pg_trgm vs combined, on a throwaway postgres:16-alpine container.

Run: <backend venv python> -I spike.py   (container p6search on 127.0.0.1:55439, password x)
Writes results.json next to this file.
"""

import asyncio
import json
import math
import random
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from corpus import QUERIES, WORKFLOWS  # noqa: E402

DSN = "postgresql://postgres:x@127.0.0.1:55439/postgres"
NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)
ME = 1

SCHEMA = """
DROP TABLE IF EXISTS workflow_steps, workflows, words CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE workflows (
  id serial PRIMARY KEY,
  user_id int NOT NULL,
  key text,
  title text NOT NULL,
  request text NOT NULL DEFAULT '',
  target_app text NOT NULL,
  status text NOT NULL,
  version_source text NOT NULL,
  created_at timestamptz NOT NULL,
  last_validated_at timestamptz,
  lang regconfig NOT NULL DEFAULT 'english',
  -- copy of the current version's instruction texts, written by the app when the current version changes
  steps_text text NOT NULL DEFAULT '',
  search tsvector GENERATED ALWAYS AS (
      setweight(to_tsvector(lang, title), 'A')
   || setweight(to_tsvector('simple', target_app), 'A')
   || setweight(to_tsvector(lang, request), 'B')
   || setweight(to_tsvector(lang, steps_text), 'C')) STORED,
  search_simple tsvector GENERATED ALWAYS AS (
      setweight(to_tsvector('simple', title), 'A')
   || setweight(to_tsvector('simple', target_app), 'A')
   || setweight(to_tsvector('simple', request), 'B')
   || setweight(to_tsvector('simple', steps_text), 'C')) STORED,
  search_text text GENERATED ALWAYS AS (title || ' ' || target_app || ' ' || request || ' ' || steps_text) STORED
);
CREATE TABLE workflow_steps (
  workflow_id int REFERENCES workflows(id) ON DELETE CASCADE,
  seq int, instruction_text text, PRIMARY KEY (workflow_id, seq)
);
"""
INDEXES = """
CREATE INDEX ix_wf_search ON workflows USING gin (search);
CREATE INDEX ix_wf_search_simple ON workflows USING gin (search_simple);
CREATE INDEX ix_wf_title_trgm ON workflows USING gin (title gin_trgm_ops);
CREATE INDEX ix_wf_text_trgm ON workflows USING gin (search_text gin_trgm_ops);
CREATE INDEX ix_wf_user ON workflows (user_id, created_at);
ANALYZE workflows;
-- vocabulary for typo correction (PG docs, pg_trgm "Text Search Integration")
CREATE TABLE words AS SELECT word FROM ts_stat('SELECT to_tsvector(''simple'', search_text) FROM workflows');
CREATE INDEX ix_words_trgm ON words USING gin (word gin_trgm_ops);
"""

# --- synthetic noise: other apps, same kind of sentences ---------------------------------------------------
APPS = ["jira", "notion", "slack", "trello", "grafana", "gitlab", "confluence", "asana", "figma", "linear"]
VERBS = ["Create", "Add", "Delete", "Rename", "Archive", "Share", "Invite", "Move", "Export", "Edit", "Close", "Assign"]
OBJECTS = ["board", "page", "channel", "member", "dashboard", "project", "label", "ticket", "comment", "team",
           "workspace", "sprint", "folder", "token", "integration", "alert", "pipeline", "view"]
STEP_BANK = ["Open the {o}.", "Click Settings.", "Click {v} {o}.", "Type a name for the {o}.", "Choose the {o} in the list.",
             "Open the menu at the top right.", "Confirm the change.", "Check the {o} appears in the list.",
             "Click Save.", "Pick a color.", "Type the person's email.", "Scroll to the bottom of the page."]


def synthetic(n, rng, user_id):
    rows = []
    for i in range(n):
        app, v, o = rng.choice(APPS), rng.choice(VERBS), rng.choice(OBJECTS)
        steps = [rng.choice(STEP_BANK).format(v=v, o=o) for _ in range(rng.randint(4, 8))]
        status = rng.choices(["verified", "outdated", "failed"], [0.75, 0.2, 0.05])[0]
        rows.append((user_id, None, f"{v} a {o} in {app.title()}", f"{v.lower()} {o} {i}", app, status,
                     rng.choice(["initial", "initial", "heal"]), rng.randint(0, 200), steps))
    return rows


async def load(con, extra_n, users=1):
    await con.execute(SCHEMA)
    rng = random.Random(135)
    rows = [(ME, k, t, r, a, s, src, age, st) for (k, a, t, r, s, src, age, st) in WORKFLOWS]
    for u in range(users):
        rows += synthetic(extra_n // users, rng, ME if u == 0 else 100 + u)
    for (uid, k, t, r, a, s, src, age, steps) in rows:
        created = NOW - timedelta(days=age + 5)
        validated = NOW - timedelta(days=age)
        wid = await con.fetchval(
            "INSERT INTO workflows (user_id,key,title,request,target_app,status,version_source,created_at,"
            "last_validated_at,steps_text) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id",
            uid, k, t, r, a, s, src, created, validated, "\n".join(steps))
        await con.executemany("INSERT INTO workflow_steps VALUES ($1,$2,$3)", [(wid, i + 1, x) for i, x in enumerate(steps)])
    await con.execute(INDEXES)


# --- the methods ---------------------------------------------------------------------------------------------
# All return (key, title, score) for the user's workflows, best first, limit 10.
STATUS_W = "CASE WHEN status='verified' AND version_source<>'heal' THEN 1.0 WHEN status='verified' THEN 0.95 " \
           "WHEN status='outdated' THEN 0.6 ELSE 0.3 END"
FRESH_W = "(0.8 + 0.2 * exp(-extract(epoch FROM ($2::timestamptz - coalesce(last_validated_at, created_at))) / 86400 / 30))"

OR_QUERY = "to_tsquery('simple', coalesce(nullif(array_to_string(tsvector_to_array(to_tsvector('{cfg}', $1)), ' | '), ''), 'xx_nothing'))"

METHODS = {
    # websearch syntax, every word must match (AND)
    "fts_and": """SELECT key,title, ts_rank_cd(search, q, 32) s FROM workflows, websearch_to_tsquery('english',$1) q
                  WHERE user_id=$3 AND search @@ q ORDER BY s DESC, id LIMIT 10""",
    # same words, any may match (OR), cover-density rank
    "fts_or": f"""SELECT key,title, ts_rank_cd(search, q, 32) s FROM workflows, {OR_QUERY.format(cfg='english')} q
                  WHERE user_id=$3 AND search @@ q ORDER BY s DESC, id LIMIT 10""",
    "fts_or_simple": f"""SELECT key,title, ts_rank_cd(search_simple, q, 32) s FROM workflows, {OR_QUERY.format(cfg='simple')} q
                  WHERE user_id=$3 AND search_simple @@ q ORDER BY s DESC, id LIMIT 10""",
    # trigram: best matching word-window anywhere in the text; <% uses the GIN index (threshold 0.6 default)
    "trgm_word": """SELECT key,title, word_similarity($1, search_text) s FROM workflows
                  WHERE user_id=$3 AND $1 <% search_text ORDER BY s DESC, id LIMIT 10""",
    "trgm_title": """SELECT key,title, similarity($1, title) s FROM workflows
                  WHERE user_id=$3 AND title % $1 ORDER BY s DESC, id LIMIT 10""",
    # combined: candidates from FTS(OR) or trigram on the title; score 0.7*fts + 0.3*title trigram
    "combined": f"""WITH q AS (SELECT {OR_QUERY.format(cfg='english')} q)
                  SELECT key,title, 0.7*ts_rank_cd(search, q.q, 32) + 0.3*word_similarity($1, title) s
                  FROM workflows, q WHERE user_id=$3 AND (search @@ q.q OR $1 <% search_text)
                  ORDER BY s DESC, id LIMIT 10""",
}
# final ranking = text score * status weight * freshness weight
METHODS["combined_ranked"] = METHODS["combined"].replace(
    "0.7*ts_rank_cd(search, q.q, 32) + 0.3*word_similarity($1, title) s",
    f"(0.7*ts_rank_cd(search, q.q, 32) + 0.3*word_similarity($1, title)) * {STATUS_W} * {FRESH_W} s")
for m in list(METHODS):
    if "$2" not in METHODS[m]:
        METHODS[m] = METHODS[m].replace("WHERE user_id=$3", "WHERE $2::timestamptz IS NOT NULL AND user_id=$3")


async def spellfix(con, q):
    """Replace words not in the vocabulary by the closest vocabulary word (similarity >= 0.45)."""
    out = []
    for w in q.lower().replace("?", " ").split():
        if len(w) < 4 or await con.fetchval("SELECT 1 FROM words WHERE word=$1", w):
            out.append(w)
            continue
        best = await con.fetchrow("SELECT word, similarity(word,$1) s FROM words WHERE word % $1 ORDER BY s DESC LIMIT 1", w)
        out.append(best["word"] if best and best["s"] >= 0.45 else w)
    return " ".join(out)


async def run_method(con, m, q):
    if m.endswith("+spell"):
        q = await spellfix(con, q)
        m = m.removesuffix("+spell")
    return await con.fetch(METHODS[m], q, NOW, ME)


async def evaluate(con, label):
    res = {}
    for m in list(METHODS) + ["combined_ranked+spell"]:
        hits, per_q, lat = 0, [], []
        for q, rel in QUERIES:
            rows = await run_method(con, m, q)
            top = [r["key"] or r["title"] for r in rows[:3]]
            ok = any(k in rel for k in top)
            hits += ok
            per_q.append({"q": q, "hit": ok, "top3": top})
            ts = []
            for _ in range(15):
                t0 = time.perf_counter()
                await run_method(con, m, q)
                ts.append((time.perf_counter() - t0) * 1000)
            lat.append(statistics.median(ts))
        res[m] = {"top3_hits": f"{hits}/{len(QUERIES)}", "median_ms": round(statistics.median(lat), 2),
                  "max_ms": round(max(lat), 2), "per_query": per_q}
        print(f"[{label}] {m:24s} top3 {hits}/{len(QUERIES)}  median {statistics.median(lat):.2f} ms  max {max(lat):.2f} ms")
    return res


async def sizes(con):
    rows = await con.fetch("""SELECT c.relname, pg_relation_size(c.oid) b FROM pg_class c
        WHERE c.relname IN ('workflows','workflow_steps','ix_wf_search','ix_wf_search_simple','ix_wf_title_trgm',
        'ix_wf_text_trgm','ix_words_trgm') ORDER BY 1""")
    toast = await con.fetchval("SELECT pg_total_relation_size('workflows') - pg_indexes_size('workflows')")
    return {r["relname"]: r["b"] for r in rows} | {"workflows_heap_plus_toast": toast}


async def main():
    con = await asyncpg.connect(DSN)
    out = {"pg": await con.fetchval("SELECT version()"),
           "extensions": [dict(r) for r in await con.fetch(
               "SELECT name, default_version FROM pg_available_extensions WHERE name IN ('pg_trgm','vector','unaccent','fuzzystrmatch')")]}

    # 1) relevance on the realistic corpus alone + 1000 synthetic workflows of the same user
    await load(con, 0)
    out["n30"] = await evaluate(con, "30")
    await load(con, 1000)
    out["n1030"] = await evaluate(con, "1030")
    out["sizes_1030"] = await sizes(con)
    out["explain_1030"] = [r[0] for r in await con.fetch("EXPLAIN (ANALYZE, BUFFERS) " + METHODS["combined_ranked"],
                                                          "add colaborator", NOW, ME)]
    # snippet cost: ts_headline on the top 10 only
    t0 = time.perf_counter()
    for _ in range(20):
        hl = await con.fetch(f"""WITH top AS ({METHODS['combined_ranked']})
            SELECT t.key, ts_headline('english', w.steps_text, websearch_to_tsquery('english', $1),
              'MaxFragments=1,MaxWords=12,MinWords=4,StartSel=<mark>,StopSel=</mark>') h
            FROM top t JOIN workflows w ON w.key IS NOT DISTINCT FROM t.key AND w.title=t.title AND w.user_id=$3""",
                             "add a collaborator", NOW, ME)
    out["headline_ms_per_query"] = round((time.perf_counter() - t0) * 1000 / 20, 2)
    out["headline_example"] = [dict(r) for r in hl[:3]]

    # 2) scale: 20 000 workflows over 20 users (1 000 each) - per-user filter
    await load(con, 20000, users=20)
    out["n20k_20users"] = await evaluate(con, "20k/20u")
    out["sizes_20k"] = await sizes(con)

    # 3) translated step text (#132): english config on Spanish text vs a per-row language config
    await con.execute("""INSERT INTO workflows (user_id,key,title,target_app,status,version_source,created_at,steps_text,lang)
        VALUES (1,'es_collab','Añadir un colaborador a un repositorio','gitea','verified','initial',now(),
        'Abre tu repositorio. Haz clic en Configuración. Abre la pestaña Colaboradores. Haz clic en Añadir colaborador.','spanish')""")
    out["lang_test"] = {
        "english_cfg_on_spanish": await con.fetchval("SELECT to_tsvector('english','Añadir colaboradores a los repositorios')::text"),
        "spanish_cfg": await con.fetchval("SELECT to_tsvector('spanish','Añadir colaboradores a los repositorios')::text"),
        "spanish_row_found_by_spanish_query": await con.fetchval(
            "SELECT count(*) FROM workflows WHERE key='es_collab' AND search @@ websearch_to_tsquery('spanish','añadir colaborador')"),
        "spanish_row_found_by_english_query": await con.fetchval(
            "SELECT count(*) FROM workflows WHERE key='es_collab' AND search @@ websearch_to_tsquery('english','add collaborator')"),
    }
    await con.close()
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())

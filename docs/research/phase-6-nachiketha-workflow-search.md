# Workflow knowledge base: search across a user's verified workflows

- **Phase:** 6 (#135)
- **Researched by:** Nachiketha's area, covered by Vishwas (research and spike run by Claude Code on Vishwas's laptop, 2026-11-19; decisions by the humans)
- **Question(s):** How do we search all of a user's verified workflows ("how do I add a collaborator on GitHub?")
  and rank the results by relevance, validation status and freshness? Postgres full-text search, trigrams, or a
  vector index?

## Findings

### What we store today [verified by reading the code]

- `workflows` has `title`, `target_app`, `target_url`, `status`, `user_id`, `current_version_id`
  (`backend/app/db/models.py:183-191`). There is **no request text** on the row. The prompt lives on
  `tasks.prompt` (`models.py:89`), reached through `workflows.task_id`.
- Step text is `workflow_steps.instruction_text` (`models.py:346`), one row per step **per version**
  (`version_id`, `models.py:341`). The shown steps are the ones whose `version_id = workflows.current_version_id`
  (`models.py:198-203`).
- The current version changes in three places: `repositories.py:253` (first version), `repositories.py:331`
  (new version) and `runs/reviews.py:178` (accepting a review). A search copy of the step text must be refreshed in
  all three.
- "Last validated" is `validations.ran_at` (`models.py:276`), with an index on `(workflow_id, ran_at)`
  (`models.py:263`). It isn't copied onto `workflows`.
- `auto-updated` is not a status: it is `status = verified` with `current_version.source = 'heal'`
  (`contracts/CHANGELOG.md` 1.13, `api/convert.py:157`).
- Titles are general since #389/#390 ("Add a collaborator to a repository"), and step text says "your repository".
  The prompt (`tasks.prompt`) still has the user's own names ("add bob to krama-bench/demo"). That's fine to search,
  because search is per user, but it must never appear in a shared tutorial.

### The list API and page today [verified by reading the code]

- `GET /workflows?target_app&limit&cursor` (`api/workflows.py:138-153`, `docs/api-contract.md:41`), newest first,
  keyset cursor on `(created_at, id)` (`repositories.py:206-226`). No text filter, no status filter.
- The frontend sends `?status=` (`frontend/lib/api.ts:612`), but the backend has no such parameter, so FastAPI
  ignores it. A small side bug, separate from #135.
- The library page (`frontend/app/(app)/tutorials/page.tsx` → `components/tutorials/TutorialLibraryView.tsx`) loads
  **up to 100** workflows (`lib/api.ts:661`) and searches them **in the browser** with `includes()` on title,
  description, prompt and target (`TutorialLibraryView.tsx:93-114`). With the real API, `taskPrompt` is just the title
  (`lib/api.ts:665`), so today the search only sees titles. It never sees step text, and workflow 101 onwards is
  never searched.

### Database image [verified: throwaway container]

- `infra/docker-compose.yml:6` uses `postgres:16-alpine`, with a 512 MB `mem_limit` (`:15`). The local image is
  **PostgreSQL 16.15**.
- Available extensions: **`pg_trgm` 1.6**, `unaccent` 1.1, `fuzzystrmatch` 1.2. **`vector` (pgvector) is not in the
  image.**
- Text search configs include `english`, `simple`, `spanish`, `german`, `french`, `hindi`, `tamil` and others
  (`pg_ts_config`).

### Spike [verified locally; scripts and results in `assets/phase-6-search/`: `spike.py`, `spike2.py`, `corpus.py`, `results.json`, `results2.json`, `spike2-output.txt`]

Setup: a throwaway `postgres:16-alpine` on 127.0.0.1:55439, removed afterwards. The table is shaped like
`workflows` plus a copied `steps_text`. There are **32 realistic workflows** (Gitea and GitHub: create repo, add
collaborator ×2, visibility ×2, branch protection ×2, webhook, delete, invite to org ×2, labels, SSH key, …; 2-7
steps each in today's instruction style) and **12 queries** with known right answers. Noise came from 1,000
synthetic workflows for other apps (Jira, Slack, Notion, … with the same verbs: "Rename a folder in Slack"), and
for scale from 20,000 workflows over 20 users. A query is a "hit" if a right workflow is in the top 3. Latency is
the median of 15 runs per query from the host through asyncpg, so it includes the Docker round trip.

The generated column (one row, no joins):

```sql
search tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector(lang, title), 'A') || setweight(to_tsvector('simple', target_app), 'A')
 || setweight(to_tsvector(lang, request), 'B') || setweight(to_tsvector(lang, steps_text), 'C')) STORED
```

`lang` is a `regconfig` column. `to_tsvector(regconfig, text)` is immutable, so a per-row language works in a
generated column [verified].

| Method | Top-3 hits, 32 wf | Top-3 hits, 1,032 wf | Median / worst ms (1,032) |
|---|---|---|---|
| FTS, `websearch_to_tsquery` (all words must match) | 8/12 | 8/12 | 0.5 / 0.6 |
| FTS, any word matches (OR), `ts_rank_cd` | 10/12 | 9/12 | 2.7 / 36 |
| FTS OR, `simple` config | 11/12 | 9/12 | 3.7 / **141** |
| Trigram `word_similarity` on all text | 8/12 | 8/12 | 0.6 / 4 |
| Trigram `similarity` on title | 7/12 | 7/12 | 0.6 / 1 |
| **Combined**: FTS OR + trigram, `0.7·fts + 0.3·title trigram` | **12/12** | 11/12 | 3.8 / 46 |
| Combined × status × freshness (proposal below) | 11/12 | 10/12 | 4.1 / 49 |
| …+ AND first, then OR if < 3 results | 11/12 | 10/12 | 3.1 / 12 |
| …+ AND-then-OR + a small synonym map | **12/12** | **12/12** | 5.3 / 78 |

With 20,000 workflows over 20 users (1,000 each), the numbers were the same within ~1-2 ms: 12/12 and
median 5.4 ms for the last row.

What each method gets wrong:
- **AND** finds nothing for `add colaborator` (typo), `rename repo` ("repo" ≠ "repository": the English stemmer
  doesn't map it), `invite someone` and `give someone access to my repository`.
- **Trigrams alone** miss long questions (`how do I add a collaborator on GitHub?`) and other wording
  (`tag an issue as bug`).
- **OR** finds the typo query only through trigrams. With noise, `rename repo` ranks "Rename a view in Linear" first
  because "repo" doesn't match.
- **`give someone access to my repository`** is a meaning match, not a word match. Only the synonym map
  (`access → collaborator member`) or embeddings find it. The map has 11 general entries (repo, pr, someone, tag,
  private, access, …). It was written knowing the test queries, so **12/12 overstates** how it does on new queries.
- **Spell fix** (PG docs pattern: a `words` table from `ts_stat` plus `similarity`) added nothing on top of
  combined, because the trigram term already handles typos in titles. It cost +1.5 ms.
- **`simple` config with OR**: stop words ("a", "my", "how") match every row, so it ranks the whole table (141 ms).
  With OR, `english` (or any config with stop words) is needed.
- **Slow cases** are OR queries with common step words: "open a new issue" OR-matches 721 of 1,032 rows (every step
  says "Open your repository"). Each candidate is scored, which costs ~50-75 ms. AND-first avoids this when AND
  already finds 3.
- **Snippet**: `ts_headline` on the top 10 adds about 8 ms per query in total. Example output: "Click
  `<mark>Add</mark> <mark>Collaborator</mark>`." Run it only on the returned page, never on all matches.
- **Prefix** (`to_tsquery('english','collab:*')`) finds both collaborator workflows, so search-as-you-type works.
- **Index size**, 1,032 workflows: FTS GIN **112 KB**, title trigram GIN 112 KB, full-text trigram GIN 344 KB,
  table 1.0 MB. At 21,032 workflows: FTS GIN **976 KB**, title trigram 1.6 MB, full-text trigram 4.8 MB, table
  20 MB. That's tiny next to the 512 MB container limit.

### Languages (#132) [verified in the spike]

- `english` on Spanish text keeps the words unstemmed (`'añadir' 'colaborador' 'los'`). `spanish` stems them and
  drops stop words (`'añad' 'colabor' 'repositori'`).
- A Spanish row with `lang = 'spanish'` is found by `websearch_to_tsquery('spanish','añadir colaborador')` but **not**
  by the English query `add collaborator`. A query has to be parsed with the same config as the text it's matched
  against, and translated text matches only queries in its own language.
- So, if #132 stores translations, either keep the search on the **original-language** text (one `lang` per
  workflow, the language the user writes in), or add one tsvector per stored language and query with the
  user's UI language. Trigrams don't depend on language, so they still catch partial and accented matches.
  `unaccent` exists, but using it inside a generated column needs an immutable wrapper function [unverified].

### Other options

- **pgvector + embeddings.** Not in `postgres:16-alpine`, so we'd need a different image
  (`pgvector/pgvector:pg16` [unverified tag]) or to build the extension ourselves. Embeddings would come from Gemini
  `gemini-embedding-001`. The free tier is reported on Google's forum as ~100 RPM / 1,000 requests a day, batch mode
  is not free, and users report 429s and quota stuck at 0 [unverified: forum posts, not the docs]. Each workflow
  needs an embedding when it's stored or changed, and **each search query needs one too**. That's an LLM round trip
  (hundreds of ms [unverified]) and quota on every keystroke, and search breaks when the key is rate-limited. Tests
  would need a fake embedder. A CPU local model (e.g. a small sentence-transformer) adds ~100-500 MB RAM [unverified].
  It helps only with meaning-match queries like "give someone access", which the synonym map covered in the spike.
  Not worth it now. Keep it as a later add-on behind the same endpoint.
- **External engines** (Meilisearch, Typesense, OpenSearch): typo tolerance and synonyms come built in, but they add
  another service, a sync job from Postgres and a copy of every workflow. That's a poor fit for a 16 GB laptop and
  for per-user filtering, at our scale (tens to hundreds of workflows per user) where Postgres answers in single-digit ms.
  Meilisearch's RAM use [unverified].

### Ranking proposal

`score = text × status × freshness`, computed in SQL and checked in the spike (`spike.py`, `STATUS_W` / `FRESH_W`):

- **text** = `0.7 · ts_rank_cd(search, q, 32) + 0.3 · word_similarity(q, title)`. Normalisation 32 maps the rank to
  0..1. Weights A=title and app, B=prompt, C=step text use PG's defaults (1.0 / 0.4 / 0.2 / 0.1).
- **status** = verified 1.0 · auto-updated (verified + heal) 0.95 · outdated 0.6 · failed 0.3. Draft, approved and
  running aren't stored workflows. A pending review (`heal_pending`) could get 0.8 once the summary exposes it.
- **freshness** = `0.8 + 0.2 · exp(-days_since_last_validation / 30)`, using `max(validations.ran_at)` or else
  `created_at`. A workflow checked today gets ×1.0, at 30 days ×0.87, and it never drops below ×0.8. Freshness only
  breaks near-ties; it can't push an exact match below a weak one.
- Effect in the spike: status and freshness cost one top-3 hit on the realistic set. The query was `give someone
  access` before synonyms, where all three candidates were weak matches anyway. With synonyms the ranked version
  hit 12/12. An exact match that is `outdated` still shows up (`invite_org_gh` in the top 3 for "invite someone"),
  just lower, and the card shows its badge.

## Recommendation

1. **Postgres only: FTS (`english`) + `pg_trgm`, combined.** No new service, no new image, no quota. It was 12/12 on
   the realistic set, 5 ms median, and < 80 ms worst case at 1,000 workflows per user. `pg_trgm` is already in the
   image. `CREATE EXTENSION pg_trgm` needs a superuser or a trusted extension; pg_trgm is marked trusted since
   PG 13 [unverified for our role setup; the compose user is the superuser].
2. **Copy the searchable text onto `workflows`**: a new `search_steps text` (the current version's
   `instruction_text`s joined by newlines) and `search_request text` (from `tasks.prompt`). Plus a **generated stored
   `search tsvector`** (title A, target_app A, request B, steps C) with a **GIN** index, and a **GIN trigram** index
   on `title` (and optionally on a generated `search_text`). Postgres generated columns can't read other tables, so
   the copy is written by the repository in the three places that change `current_version_id`. A trigger is the
   alternative, but it hides the logic, and this codebase keeps writes in `repositories.py`.
3. **Query = AND first, then OR + trigram if fewer than 3 results, plus a small general synonym map in Python**
   (repo/repository, pr/pull request, someone/person/member, …), kept in the search module with a unit test. Prefix
   match on the last word for search-as-you-type.
4. **Rank = text × status × freshness** with the numbers above. Return only the user's workflows, statuses verified,
   outdated and failed. Show the top match's matching step via `ts_headline` on the returned page only.
5. **`GET /workflows?q=`** on the existing list instead of a new `/search`. Without `q`, nothing changes (newest
   first, cursor). With `q`, it returns results by score with offset-style paging (`limit ≤ 50`, no cursor:
   relevance has no stable keyset). Each `WorkflowSummary` gets optional `match`: `{ step_seq, snippet }` (snippet
   with `<mark>` only, which the frontend must render as text plus marks, never as raw HTML), `score`, and
   `last_validated_at`. Additive → **contracts 1.15**, `workflow.schema.json` v1.3.
6. **Frontend**: the library's search box calls the API with `q` (debounced ~250 ms) instead of filtering 100 items
   in the browser. Status pills become `?status=` (fixes the ignored parameter). Show the snippet under the title.
7. **Embeddings later, not now.** Revisit when users have hundreds of workflows and report meaning-match misses.
   It would need an ADR (new image, Gemini quota on every query).

## Proposed decisions

| # | Proposal | Options | Recommendation | Applies to |
|---|---|---|---|---|
| S1 | Search engine | Postgres FTS / pg_trgm / both / pgvector + Gemini / Meilisearch | **FTS + pg_trgm**, no new service | backend db, infra (none) |
| S2 | Where the step text lives | copy column written by the repository / trigger / join at query time | **copy columns** `search_steps`, `search_request` + generated `search` tsvector, updated where `current_version_id` changes | `db/models.py`, `repositories.py`, `runs/reviews.py`, new migration |
| S3 | Text search config | `english` / `simple` / per-row `regconfig` | **per-row `lang regconfig` default `english`**; with OR queries, never `simple` (stop words) | migration; #132 later |
| S4 | Query shape | AND only / OR only / AND-then-OR, ± synonyms, ± spell fix | **AND-then-OR + trigram + small synonym map**; no spell-fix table | backend search query |
| S5 | Ranking | text only / × status / × status × freshness | **text × status (1.0/0.95/0.6/0.3) × freshness (0.8 + 0.2·e^(−days/30))** | backend search query |
| S6 | API | `GET /workflows?q=` / new `GET /search` | **`?q=` on `/workflows`** + `status` filter; offset paging when `q` is set | `api/workflows.py`, `docs/api-contract.md` |
| S7 | Contract | none / additive | **1.15 additive**: `WorkflowSummary.match {step_seq, snippet}`, `score`, `last_validated_at` (all optional/nullable) | `contracts/` (contract-change PR) |
| S8 | Frontend | keep client-side filter / server search | **server search**, debounced, snippet under title, status pills → `?status=` | `frontend/components/tutorials/*`, `lib/api.ts` |
| S9 | Embeddings | now / later / never | **later, behind the same endpoint, with an ADR** | — |
| S10 | Translations (#132) | search original only / one tsvector per language | **original language only** until #132 lands; decide in #132 | #132 |

## Task issues it would split into

| Task | Size | Contract change? |
|---|---|---|
| Contract 1.15: `GET /workflows` `q` and `status` params, `WorkflowSummary.match/score/last_validated_at`, fixture with a match | S | **yes** (contract-change PR) |
| Migration: `CREATE EXTENSION pg_trgm`, `search_steps`/`search_request`/`lang` columns, generated `search` tsvector, GIN + trigram GIN, backfill from current steps and `tasks.prompt` | M | no |
| Repository: keep the search copy in sync in the 3 write paths (`repositories.py:253`, `:331`, `runs/reviews.py:178`) + tests | S | no |
| Search query + ranking (AND-then-OR, trigram, synonyms, status × freshness, `ts_headline` on the page) + `?q=`/`?status=` on `GET /workflows` + tests against real Postgres | M | no (uses 1.15) |
| Frontend: server-side search box (debounce), snippet, status pills via `?status=`, mock API support | M | no (uses 1.15) |
| Small: backend accepts `?status=` the frontend already sends (if split out from the above) | S | yes (folded into the 1.15 PR) |
| Later: embeddings spike (pgvector image, Gemini embedding quota, fake embedder) | M | ADR first |

## Open questions

- Should failed workflows appear in search at all, or only verified and outdated ones?
- Should search cover the prompt (`tasks.prompt`)? It has the user's real names, which helps them find things, but a
  snippet from it must never be shown on a shared tutorial page.
- Real queries: collect the first ~50 real searches (count only, no text, or with consent) to tune the synonym map
  instead of guessing.

## Links
- https://www.postgresql.org/docs/16/textsearch-controls.html (websearch_to_tsquery, ts_rank_cd, ts_headline)
- https://www.postgresql.org/docs/16/pgtrgm.html (word_similarity, `<%`, Text Search Integration)
- https://www.postgresql.org/docs/16/ddl-generated-columns.html
- https://developers.googleblog.com/gemini-embedding-available-gemini-api/
- https://discuss.ai.google.dev/t/gemini-embedding-free-tier-documentation/112553 (free-tier limits, unofficial)
- https://ai.google.dev/gemini-api/docs/rate-limits

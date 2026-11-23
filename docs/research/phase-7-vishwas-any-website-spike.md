# Phase 7 spike: Krama on unfamiliar websites, and Gemini vs a local model

- **Issue:** #457 (part of the Phase 7 idea #455). Needs the Ollama provider (#456, ADR 0010).
- **Run by:** Claude Code with Vishwas on Vishwas's laptop (Windows 11, i5-14450HX, 24 GB RAM, RTX 4050 6 GB,
  Ollama 0.17.1), 2026-11-23. Code: `main` at 8119dde plus #456 (the run path is unchanged by #456).
- **Scripts and results:** [`assets/phase-7-vishwas-any-website/`](assets/phase-7-vishwas-any-website/). Page
  snapshots and prompts are not committed (third-party page text); `part_b.py capture` rebuilds them.
- **Rules kept:** public sites only, no banking, payment or other sensitive sites, no CAPTCHA met or solved, no
  account used. Real Gemini only for Part A and the Part B comparison.

## Question

Where does today's Krama break on websites it has never seen, and is a local 7B model good enough for the per-step
decisions a look-before-each-step design needs?

## Short answer

- **Krama acts correctly on unknown sites but guesses wrongly about pages it hasn't seen.** Every action it took on
  five unknown sites hit the right element. Four of five tasks still didn't finish: three failed verification on a
  *guessed* expected state of a page the planner couldn't see yet, and one never reached the right start page.
- **Five concrete gaps**, most of them small: the planner sees only `<main>` (no header search or navigation); the
  target URL's path is dropped; URL checks ignore the query string; every replan pauses for review; sign-in works
  only on pre-configured sites. Page snapshots range from 440 characters to 352,000.
- **Gemini is good at the per-step decision (17/18); qwen2.5:7b on the GPU picks the right element (17/18) but often
  the wrong action verb (strict score 12/18); llama3:8b is not usable (7/18).** On CPU only, qwen takes 15–258 s per
  decision. So a local model is a useful **development** stand-in for small and medium pages on a GPU, and not an
  option for the product or the reference laptop.
- **Recommendation:** look before each step, verify by what actually changed instead of by guessed expectations,
  and fix the small gaps first. Decisions are proposed in
  [`phase-7-decisions-alignment.md`](phase-7-decisions-alignment.md).

---

## Part A: today's code on five unknown sites (real Gemini)

**How.** The product path, like the benchmark's `ApiAgentRunner`: sign in, `POST /tasks` with the site's URL, approve
the plan, wait for the run. A pause is recorded and the run cancelled (nobody answers in the spike). The API ran
through `serve_logged.py`, which logs every LLM call (schema, model, attempts, latency, tokens). No site has hints
(`SITE_HINTS` only knows Gitea and GitHub).

| Task | Site | Outcome | Where it broke | LLM calls (attempts) | Time |
|---|---|---|---|---|---|
| Search for Alan Turing and open his article | en.wikipedia.org | ✅ verified, **but** | The plan was one step, *navigate to `/wiki/Alan_Turing`*. The search the user asked for was never shown: the search box is in the header, which the planner can't see | 2 (6) | ~3 min |
| Search the map for Bengaluru | www.openstreetmap.org | ⏸ paused | Both actions worked (title "Bengaluru \| OpenStreetMap"). Step 2 expected `query=Bengaluru` in the URL; the verifier sees the path `/search` only. The replan then paused for review | 2 (2) | 47 s |
| Add a todo called Buy milk and mark it completed | demo.playwright.dev/todomvc | ❓ question | The run opened `demo.playwright.dev/`, not `/todomvc`: the target URL's path is dropped. The planner rightly asked where the todo list is | 1 (1) | 35 s |
| Search the Python docs for `asyncio.gather` and open it | docs.python.org/3 | ⏸ paused | Step 1 worked. It expected `^/search.html$`; the page is `/3/search.html` (the `/3` was lost again). Replan paused | 2 (2) | 73 s |
| Find the MDN page for `Array.prototype.map` | developer.mozilla.org/en-US | ⏸ paused | Step 1 opened the search. It expected a searchbox named "Search MDN", a name it guessed for a dialog it had not seen. The plan and the replan were each rejected once by the plan checks and asked again | 4 (8) | 179 s |

### Breakpoints by category

| Category | What we saw | Tasks hit | Size of fix |
|---|---|---|---|
| **Blind planning** (expected states of unseen pages) | Every failed step had worked; its *guessed* expectation was wrong (URL query, URL prefix, dialog name). Same class as #449 on Gitea | 3/5 | L: needs the look-before-each-step design |
| **The planner sees only `<main>`** | `page_snapshot()` returns the `main` landmark when there is one. Header search, site navigation and account menus are invisible. Python docs: main 4,002 chars vs body 11,305 | 2/5 (Wikipedia shortcut, MDN search) | S |
| **Target URL path dropped** | `open_start_page(page)` always opens `/`, which resolves to the origin root | 2/5 (TodoMVC, Python docs; MDN redirected) | S |
| **URL checks ignore the query string** | The observer keeps `urlsplit(url).path`; any expectation on `?q=` or `?query=` can't pass | 1/5 (OSM) | S |
| **Every replan pauses** | A replan waits for "replan_review". On an unknown site the first wrong guess stops the run until a human answers | 3/5 | M (policy and UX decision) |
| **Snapshot size** | 440 chars (TodoMVC) to 352,465 (a Wikipedia article). The end-of-run task check sent **114,688 input tokens** to Gemini | 1/5 | M: trim to a budget |
| **Sign-in** | `POST /sites/{site}/sign-in` answers 404 for any site but the configured ones (`SITES` = GitHub; Gitea uses the demo login). The takeover's navigation guard only allows the target and its configured sign-in hosts, and closes popups, so "Sign in with Google" or a separate `login.` host is blocked | not runnable today | M–L |
| Locating elements | No failures: 8/8 actions hit the right element by role and name | 0/5 | — |
| Bot walls, slow pages | None on these sites (GitHub's issue list also loaded headless in Part B without a challenge) | 0/5 | — |

### Gemini on the day

- `gemini-3.8-flash` answered "high demand" (503) to every request it got; `gemini-3.5-flash` gave no answer within
  30 s to every prompt of 10,000+ characters. The fallback worked: everything was answered by `gemini-2.5-flash`.
- `gemini-2.5-flash` answered **27 requests** in the day (11 in Part A, 16 in Part B) without a 429. The "20 requests/day per
  model" figure from Phase 0 is therefore outdated for this model; the real limit is unknown **[unverified]** and
  should be measured before planning the benchmark around it.
- Today's design uses 1–4 calls per task (plan, replans, plan-check retries, the task check). A step-by-step design
  uses about one call per step plus a final check: 3–6 calls for these tasks.

---

## Part B: Gemini vs local models on the per-step decisions

**How.** 18 page states on 7 sites (`part_b.py`): Wikipedia, OpenStreetMap, TodoMVC, Python docs, MDN, and GitHub's
public issue list. Each state is opened with Playwright and its **whole `body`** ARIA snapshot is taken (what a
step-by-step agent would need; see the `<main>` finding), capped at 48,000 characters (~12k tokens) so every model
gets the same input. Two questions, structured output through Krama's own `LLMProvider`, temperature 0:

- **next** (11 cases): "the single next action toward the task" → action, target role + name, value.
- **done** (7 cases): "is the whole task complete on this page?" → evidence, yes/no. Includes traps: a different
  todo completed, search results instead of the entry, the home page.

Graded automatically against hand-written answers (several right answers allowed, e.g. click Go *or* press Enter).
"Right element" ignores the action verb and value.

| Model | Next action (strict) | Right element | Done check | Median s | Max s |
|---|---|---|---|---|---|
| Gemini (2.5-flash 16, 3.5-flash 2) | **10/11** | 10/11 | **7/7** | 9.4 | 96 |
| qwen2.5:7b, GPU | 6/11 | **11/11** | 6/7 | 7.2 | 25 |
| qwen2.5:7b, CPU only (13 smaller cases) | 4/8 | 7/8 | 5/5 | 64 | 258 |
| llama3:8b, GPU | 2/11 | 4/11 | 5/7 | 4.6 | 21 |

Per case (✅ right, ❌ wrong, seconds):

| Case | Chars sent | Gemini | llama3 GPU | qwen CPU | qwen GPU |
|---|---|---|---|---|---|
| wiki-home-next | 40,329 | ✅ 41 | ❌ 21 | — | ✅ 25 |
| wiki-typed-next | 40,720 | ✅ 28 | ❌ 11 | — | ✅ 17 |
| wiki-article-done | 48,000 (capped) | ✅ 96 | ✅ 8 | — | ✅ 17 |
| wiki-home-done | 40,329 | ✅ 4 | ❌ 7 | — | ✅ 15 |
| osm-home-next | 2,895 | ✅ 2 | ✅ 4 | ✅ 82 | ✅ 6 |
| osm-typed-next | 2,880 | ✅ 1 | ❌ 5 | ❌ 64 | ❌ 6 |
| osm-results-done | 2,596 | ✅ 2 | ✅ 4 | ✅ 68 | ✅ 7 |
| todo-empty-next | 440 | ✅ 54 | ✅ 4 | ✅ 29 | ✅ 6 |
| todo-typed-next | 450 | ❌ 9 | ❌ 4 | ❌ 15 | ❌ 4 |
| todo-added-next | 794 | ✅ 17 | ❌ 4 | ✅ 23 | ✅ 5 |
| todo-added-done | 794 | ✅ 10 | ✅ 4 | ✅ 30 | ✅ 5 |
| todo-completed-done | 867 | ✅ 9 | ✅ 2 | ✅ 24 | ✅ 4 |
| todo-other-done | 871 | ✅ 7 | ✅ 2 | ✅ 26 | ✅ 6 |
| py-home-next | 11,305 | ✅ 11 | ❌ 6 | ✅ 203 | ✅ 8 |
| py-results-next | 9,265 | ✅ 9 | ❌ 5 | ❌ 152 | ❌ 8 |
| py-results-done | 9,265 | ✅ 17 | ❌ 4 | ✅ 258 | ❌ 9 |
| mdn-home-next | 12,126 | ✅ 9 | ❌ 6 | ❌ 257 | ❌ 10 |
| gh-issues-next | 24,605 | ✅ 16 | ❌ 9 | — | ❌ 9 |

What the wrong answers were:

- **qwen2.5:7b** chose the right element every time on the GPU. Its errors: `press` or `check` on a button or link
  instead of `click` (4), `press` with no key (1), and one false "done" on a search-results page. Twice it wrote its
  `thought` in Chinese. A small normaliser (press/check on a button or link → click; press without a key → Enter)
  would turn most of its misses into hits; that is a guess until measured.
- **llama3:8b** invented elements (a link "Array.prototype.map" on MDN's home page, "navigate" with no URL), and its
  context stops at 8,192 tokens, so the Wikipedia pages were cut.
- **Gemini's** one miss is borderline: "press Enter" with no target, after typing in the todo box. In a real run this
  would work on the focused field; the grader wanted the target.
- The grader's `todo-typed-next` answer is strict for every model.
- **GPU vs CPU** qwen gave different answers on 2 cases at temperature 0.

### Whole plans: the long-reasoning gap

The exact first-planning prompts Gemini got in Part A, sent to qwen2.5:7b with the planner's system prompt and schema
(`plans.py`; results in `results/part-b/plans-qwen.json`):

| Task | Gemini | qwen2.5:7b |
|---|---|---|
| Wikipedia | 1 step: navigate to the article (shortcut) | 3 steps; uses the element id `searchInput` as the name; "press" with no target |
| OpenStreetMap | fill + click Go; guessed URL query | fill + **press** Go; guessed `^/map/.*Bengaluru$` |
| TodoMVC (wrong start page) | asked where the todo list is (right) | **invented** a `/dashboard` page, a "Create a new todo item" dialog and targets with no role |
| Python docs | 4 sensible steps; guessed URL | 4 steps; used the field id `q` as its name; guessed `asyncio/gather.html` |
| MDN | 3 sensible steps | 1 step: navigate to a URL from memory (right URL, skips the UI) |

Both models guess what unseen pages look like; qwen also invents pages and confuses ids with names. Planning a whole
task is a Gemini job.

### Speed and memory

- GPU (6 GB): qwen2.5:7b with a 16k context needs 6.5 GB, so 15 % ran on the CPU; 4–25 s per decision.
- CPU only: 15–258 s per decision (median 64 s) on a 24 GB laptop with a 14th-gen i5, ~5 GB RAM for the model. The
  reference laptop (16 GB, no GPU) would be slower and can't spare the RAM next to the stack and a browser.
- Gemini: median 9 s, but up to 96 s on the 40k+ character pages and when the first models in the chain stall.

---

## Which jobs a local model can do

| Job | Local 7B? | Why |
|---|---|---|
| Next action on a small or medium page (≤ ~12k chars), during development | ✅ with a verb normaliser | right element 11/11 on GPU |
| "Is the task done?" on a small page, during development | ✅ | 6/7; the miss was a search-results trap |
| Next action or done check on a big page (40k+ chars) | ⚠️ GPU only, slow | fits only with a 16k context, needs trimming |
| Planning a whole task | ❌ | invents pages and steps |
| Anything in the product, or on the reference laptop | ❌ | no GPU there; 1–4 min per decision on CPU (ADR 0010) |
| Tutorial text | ❌ not needed | written by code (ADR 0003) |

## Recommended Phase 7 scope

The full proposal, with options, sizes and the exit gate, is in
[`phase-7-decisions-alignment.md`](phase-7-decisions-alignment.md). In short:

1. **Fix the small gaps first** (S each): the full page (header included, trimmed to a budget) for every LLM call;
   keep the target URL's path; URL checks with the query string.
2. **Look before each step** (L): observe → decide one action → act → verify by what changed, repeated, with an
   outline the user approves first. The steps actually taken become the tutorial; risky steps still pause.
3. **Sign in to any site** (M–L): sessions keyed by site origin, sign-in hosts learned during the takeover with the
   owner's consent, generic "signed in" detection.
4. **Learned site notes** (M), then a **real-site benchmark** of 10–15 public sites as the exit gate.

## Not covered

- No task needed a free account: sign-in on an unknown site isn't possible in today's code (see above), so there was
  nothing to try without building it first.
- Five tasks and 18 states are a small sample; the per-site failures are clear, the model percentages are rough.
- The replans that paused were not allowed to run, to save Gemini quota; whether the replan would have recovered is
  unknown.

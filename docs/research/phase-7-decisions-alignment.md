# Phase 7 Decisions & Alignment: Krama on any website

- **Phase:** 7 (idea #455; spike #457; Ollama dev provider #456, done)
- **Document type:** Decision record + research summary (for Nachiketha to read; for both agents to build on)
- **Decided by:** Vishwas, 2026-11-23: **every recommended option**, chosen in the session that wrote this note.
  Nachiketha is away, so Vishwas also took the decisions in Nachiketha's areas.
- **Written by:** Claude Code on Vishwas's laptop, 2026-11-23, from
  [`phase-7-vishwas-any-website-spike.md`](phase-7-vishwas-any-website-spike.md).
- Decisions in Nachiketha's areas (`frontend/`, `packages/`, `policy/`, `observer/`, `validation/`) are marked
  **[N]**. Nachiketha: if you disagree with one, raise it on the issue it applies to.

---

## 1. Research in five minutes

On five public sites Krama had never seen, **every action hit the right element** (8/8), yet only one task verified,
and that one by jumping straight to the article URL instead of searching. Three runs failed on an *expected state the
planner guessed* for a page it hadn't seen (a URL query, a URL prefix, a dialog name); each failed step had in fact
worked. One run opened the wrong page because the **target URL's path is dropped**. The planner only sees `<main>`, so
**header search and navigation are invisible**; URL checks **ignore the query string**; **every replan pauses** for
review; and sign-in is only possible on **pre-configured sites**.

Per-step decisions over 18 page states: **Gemini 17/18**. **qwen2.5:7b** on the 6 GB GPU found the right element in
**11/11** "next action" cases but the strict score was 12/18 (wrong verbs such as `press` on a button); on CPU it took
15–258 s per decision. **llama3:8b** 7/18, inventing elements. For whole plans, qwen invents pages and steps. Gemini
2.5-flash answered 27 requests in one day without a 429, so the 20/day limit needs re-measuring; 3.8-flash was
overloaded (503) and 3.5-flash stalled on big prompts all day.

---

## 2. Decisions

Each table keeps the options that were weighed; the **bold** one was chosen.

### 2.1 How the agent works

| # | Question | Options | Recommended |
|---|---|---|---|
| W1 | Plan up front, or look before each step? | (a) keep plan-up-front, fix the gaps only; (b) look before each step everywhere, no outline; (c) **outline up front (one call, the user approves the goal and the rough steps), then observe → decide one action → act → verify, repeated** | **(c).** (a) can't fix guessed expectations, the main failure. (b) gives the user nothing to approve before Krama acts |
| W2 | One agent for every site? | (a) **the step agent for new tasks on every site, Gitea and GitHub included; replays (do it, reverify) keep the stored steps and make no LLM calls**; (b) step agent only for sites without hints | **(a)**: one code path to test; Gitea stays the CI and destructive-test site |
| W3 | How a step is verified | (a) keep the planner's guessed `expected_state`; (b) **after acting, record what actually changed (URL incl. query, new or gone elements, field values) as the step's expected state; ask the LLM "did this do what you intended?" only when nothing visible changed; one final "is the task done?" check** | **(b)**. The stored workflow then replays against real, observed states |
| W4 | What replaces "replan_review" pauses | (a) keep pausing; (b) **no replans in step mode: the next decision is the recovery. Limits: 20 steps per task, 3 decisions in a row without visible progress → pause and offer takeover** | **(b)**. Risky steps still pause (policy unchanged, AGENTS.md §4) |
| W5 | The page the LLM sees | (a) `<main>` only (today); (b) whole `body`; (c) **whole `body`, trimmed to a budget of ~24k characters (~6k tokens): interactive elements, headings and landmarks first, long text cut, dialogs always kept** | **(c)**. Also used by today's planner and the task check (the check sent 114,688 tokens) |
| W6 | Screenshots for decisions | (a) **ARIA text only; vision stays a fallback when an element can't be found (today's rule)**; (b) screenshot with every decision | **(a)**: ARIA was enough in every spike case and costs a fraction of the tokens |
| W7 | Tutorial text | **Written by code from the steps actually taken (ADR 0003 stays); the outline's wording becomes section titles** | — |
| W8 | Today's plan-up-front planner during the switch | (a) remove at once; (b) **keep it behind a setting for one release (v1.4), then remove it**; (c) keep it | **(b)** |

### 2.2 LLM use and quota

| # | Question | Options | Recommended |
|---|---|---|---|
| Q1 | Model chain for step decisions | (a) same chain as planning (3.8 → 3.5 → 2.5); (b) **its own setting `GEMINI_MODELS_STEP`, defaulting to the model that answered fastest in the spike (2.5-flash first), with the 3.x models behind it** | **(b)**, re-checked with a week of call logs |
| Q2 | Budget per task | **≤ 25 LLM calls per task (outline + ≤ 20 steps + checks); a task that hits it pauses** | — |
| Q3 | Measure the real free-tier limits | **A small job logs every Gemini call (model, status, tokens) to the DB, so the gate and the benchmark plan on measured numbers** | S |
| Q4 | Local model | **Dev only (ADR 0010), `qwen2.5:7b`, plus the verb normaliser in the step decider (press/check on a button or link → click), which also protects against the same Gemini slip** | — |

### 2.3 Sign in to any site

| # | Question | Options | Recommended |
|---|---|---|---|
| A1 | Which sites | (a) a list we maintain; (b) **any public `https` site the user names, except a denylist of sensitive kinds (banking, payments, government ID, health) checked by the policy [N]; the user confirms the site's terms allow automation** | **(b)** |
| A2 | How sessions are keyed | (a) per site name (today: `github`); (b) **per site origin (`https://host`), plus the sign-in hosts seen during that site's sign-in** | **(b)**; needs a migration and an ADR (updates ADR 0007) |
| A3 | "Who is signed in?" | (a) per-site code (today); (b) **generic: the owner presses "I've signed in", Krama compares cookies before and after (new session-like cookies) and checks the login form is gone; the account name is shown when the page shows it** | **(b)**; per-site code stays for Gitea and GitHub |
| A4 | Takeover navigation during sign-in | (a) target host only (today, T10); (b) **during a sign-in takeover, also hosts reached by a redirect or a click from the page (an SSO host), recorded as that site's sign-in hosts; private IPs, `file:` and `chrome:` stay blocked; popups open in the same tab instead of closing**; (c) any host | **(b)**: keeps the T10 SSRF guard and makes "Sign in with Google"-style flows possible |
| A5 | Whose account records a tutorial | **The user's own (their stored session), or none for public pages. Shared test accounts stay for Gitea/GitHub and the benchmark. Account names on pages are masked in tutorials [N]** | — |

### 2.4 Learned site notes

| # | Question | Options | Recommended |
|---|---|---|---|
| K1 | Where site knowledge comes from | (a) hand-written hints (today); (b) LLM-written summaries; (c) **built by code from verified workflows on the same origin: page URL patterns, headings and the names of elements used, at most ~40 lines** | **(c)**: free, deterministic, testable; passed to the LLM as untrusted data (it comes from pages). Gitea and GitHub hints stay as seeds |

### 2.5 UI [N]

| # | Question | Recommended |
|---|---|---|
| U1 | Starting a task | **Any URL field (today it is a site picker); "Sign in to this site" when the site needs it** |
| U2 | Approval | **Outline approval page (goal + rough steps + "risky steps will ask you"), instead of the per-step plan review for new tasks** |
| U3 | Live run | **Each decision shows what Krama saw and why it chose the action (the `thought`, one line), and the takeover button stays** |

### 2.6 Process

- Batches as in Phase 6: one branch and PR per batch, contract changes as the first commits (approved exception to
  AGENTS.md rule 3), self-merge when CI is green.
- Development runs use `LLM_PROVIDER=ollama`; real Gemini only at checkpoints and the gate.
- Vishwas builds everything, Nachiketha's areas with `KRAMA_CROSS_EDIT=1` and the `cross-boundary` label.

---

## 3. Issues and sizes

| Batch | Issue | Size | Notes |
|---|---|---|---|
| **A: quick fixes** (worth it even without the rest) | Full-page snapshot trimmed to a budget, for the planner and the task check (W5) | M | |
| | Keep the target URL's path as the start page | S | |
| | URL checks include the query string | S | stored `url_matches` stay valid |
| | Log every LLM call to the DB (Q3) | S | |
| **B: step agent** | ADR: look before each step (W1–W4) | S | |
| | contract: outline, run mode, `step.decided` event, step budget | S | contract-change |
| | Outline planner (one call) | M | |
| | Step decider (one action per call, verb normaliser) | M | |
| | Verify by observed change; final done check (W3) | M | |
| | Executor loop: decide → act → verify, limits, pause on no progress (W4) | L | |
| | Stored workflow and tutorial from the steps taken | M | |
| | Frontend: outline approval, live decisions (U2, U3) | M | [N] |
| **C: any-site sign-in** | ADR: sessions per origin, generic sign-in (updates ADR 0007) | S | |
| | contract: site by origin, sign-in hosts | S | contract-change |
| | Origin-keyed sessions + migration (A2) | M | |
| | Generic "signed in" check (A3) | M | |
| | Takeover guard for sign-in hosts, popups in the same tab (A4) | S | |
| | Policy: sensitive-site denylist (A1) | S | [N] |
| | Frontend: any URL, "Sign in to this site" (U1) | M | [N] |
| **D: site notes** | Site notes from verified workflows (K1) | M | |
| **E: benchmark + gate** | Real-site benchmark runner and task file (10–15 sites) | M | |
| | Exit gate | M | |

Roughly 2 L, 13 M, 10 S.

---

## 4. Exit gate (v1.4)

On a 16 GB CPU-only laptop, free tiers only, real Gemini; CI uses fakes.

- **Real sites:** a held-out set of **12 public sites, 2 tasks each** (8 sites without an account, 4 with a free
  account the owner signs in to by hand). **≥ 18/24 tasks verified**, with at most one takeover each; every stored
  tutorial replays once (do it for me or reverify) without an LLM call.
- **No regressions:** the Gitea benchmark at or above its v1.3 rate; the Phase 6 do-it-for-me and takeover checks pass.
- **Safety:** every destructive step pauses; no CAPTCHA solved or bypassed; sensitive sites refused; no secrets or
  account names in artifacts; tutorials universal.
- **Cost:** median ≤ 10 LLM calls per task; a decision's p50 ≤ 15 s on Gemini; RAM within the 16 GB laptop with the
  stack, the API and one browser.

## 5. Still open

- Which free accounts to use for the 4 signed-in sites (the owner's own accounts; no shared test accounts).
- The real daily limit of `gemini-2.5-flash` (Q3 measures it).

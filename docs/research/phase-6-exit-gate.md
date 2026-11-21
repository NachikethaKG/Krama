# Phase 6 exit gate (#431)

- **Run by:** Claude Code with Vishwas on Vishwas's laptop (Windows 11, i5-14450HX, 24 GB RAM, CPU only), 2026-11-21.
- **Criteria:** [phase-6-decisions-alignment.md §3](phase-6-decisions-alignment.md#3-exit-gate-v13).
- **Rules:** real Gemini and GitHub only here; everything else ran against the local stack (`just up`: Postgres, Redis, Gitea).

## Result

| Area | Criterion | Result |
|---|---|---|
| Search | right workflow in the top 3 for ≥ 10/12 held-out queries | ✅ 11/12 |
| Search | outdated ranked below verified | ✅ (`test_outdated_ranks_below_verified_for_the_same_words`) |
| Search | p95 < 100 ms at 1,000 workflows | ✅ 70–77 ms for the search query; see the note |
| Languages | UI in English + Hindi | ✅ server renders `lang="hi"` with the Hindi messages |
| Languages | one tutorial played in Hindi (captions), exported in German (narrated), quoted labels unchanged | ✅ after fixes 2 and 3 |
| Do it for me | ≥ 8/10 Gitea replays with new values, checked in Gitea | ✅ 8/10, plus 2/2 extra |
| Do it for me | every destructive step pauses | ✅ each of 38 attempts at the delete step paused before acting |
| Do it for me | no secrets in artifacts | ✅ no demo password in any file of the 12 runs |
| Do it for me | one GitHub checkpoint run | see below |
| Takeover | a run paused at a Gitea login wall is finished by hand, resumes, completes | ✅ the sign-in run, after fixes 8–12 |
| Takeover | the human-done step shows as "do it yourself" | ⚠️ not shown: see "Not covered" |
| Takeover | screencast ≤ 300 MB extra RAM | ✅ about 225 MB (the takeover browser: 4 processes); the API process stayed at about 138 MB in total |

## Measurements

**Search.** 1,000 workflows: the 12-workflow test corpus plus 988 noise workflows built like the spike's (other apps,
the same kind of step text; 75 % verified, 20 % outdated, 5 % failed). The 12 held-out queries from
`tests/api/test_search.py` were each run 20 times (240 samples) and 10 times through `search_workflows` alone.

- Hits: 11/12. The miss is "let alex push to my repo" (wanted "Add a collaborator to a repository").
- Search SQL: p50 6–7 ms, p95 70–77 ms. The slowest queries are "invite someone to the organization" (about 72 ms;
  its synonyms match hundreds of noise rows) and "open PR" (about 44 ms).
- Through the API (in-process test client): p95 123–140 ms. A plain `GET /workflows` without a query already takes
  about 59 ms there (client, auth, serialisation), so the gate counts the search query itself, as the spike did.

**Languages.** Workflow "Create a private repository in an organization", 3 steps, real Gemini.

- Hindi and German translations ready in 6–12 s. All steps translated; every quoted label unchanged.
- Hindi export: captions in Hindi, silent audio (max −91 dB). German export: German captions, Thorsten voice
  (max −3 dB).

**Do it for me.** 10 replays over 8 stored Gitea workflows with new values: 2 repositories, 2 issues, 2 branches,
a comment, a description, a file, and a branch with a file. Each was checked through the Gitea API, not through
Krama.

- 8 verified and confirmed. Each took about 6 s.
- The 2 failures were the same stored workflow (`9a5e3ac1`). Its revision 2 came from a self-heal demo that had
  renamed the button to "Make Repository"; real Gitea says "Create Repository". Krama found the real button but
  refused to click a different name (`ambiguous_target`), which is the intended safe behaviour.
- 2 extra replays of a normal create-repository workflow (`99005f28`): both verified and confirmed.

**Destructive step.** Recorded task "Delete the repository gate-repo-…-c", planned by Gemini.

- Step 3, "Click Delete This Repository", paused with `destructive_action` every time, before acting.
- After it was allowed, Gitea's confirmation modal opened. But the plan expected a dialog named "Delete Repository",
  and the modal says "Delete This Repository". So the verifier failed a step that had worked, and Krama never
  retried the high-risk step on its own. Filed as #449.

## Fixes found by the gate (PR for #431)

1. Search: rank first, then find the snippet step only for the page (it ran for every candidate).
2. Export: the job lost the export's language (`export_out`), so every export came out in English.
3. Translation: labels in straight quotes (`"New repository"`) were translated; they are protected now
   (prompt version `tokens-2`).
4. API: the 127.0.0.1 dev frontend was not an allowed origin (sign-in answered 403).
5. Frontend: the Next.js dev server served 127.0.0.1 without hydrating (`allowedDevOrigins`).
6. Frontend: the repo-root `.env` never loaded (`@next/env` cache), so the app always ran on mock data.
7. Frontend: real Devanagari and Kannada fonts, normal letter spacing for Indic scripts, and a header that fits any
   language (icon tabs when labels don't fit, a compact language menu).
8. Sign-in run: it paused without a current step, so allow and deny on the pause answered 409.
9. Takeover: a viewer's disconnect ended the takeover at once. It now ends after 5 s without a viewer, so a reload
   or React's double effect in dev re-attaches.
10. Takeover viewer: a closed socket's late close event showed "the takeover ended" over the live view.
11. Run page: a new API client on every render (the timer ticks each second) reconnected the screen every second.
12. Gitea sign-in check: Gitea's API answers 401 to a browser session, so Krama never saw anyone signed in. It now
    reads the account from `/user/settings`.

Fixes 2–4 and 8–12 add tests (2 was confirmed to fail without the fix). Fix 1 is covered by the existing search tests
and the timing above. Fixes 5–7 were checked by hand in a headless browser: hydration, real API calls, and header
screenshots in English, Hindi and Kannada at 900–1440 px.

## Not covered, and follow-ups

- **"Do it yourself" step in a tutorial.** The only login wall left after signing in was the sign-in run itself,
  and that run stores no workflow. Showing a human-done step needs a recorded task that hits a wall mid-run while
  the user has no stored session. The flow is covered by `tests/api/test_takeover_flow.py`.
- **Sign-in UX** (seen during the gate):
  - The sign-in pause shows "Continue" and "Waiting for you to confirm a step". It should say: sign in here, in
    Krama's browser, then press I'm done.
  - The finished sign-in run looks like a failed task.
  - After signing in, the user is not taken back to the task.
  - A new run waits silently behind a paused one (`MAX_CONCURRENT_RUNS=1`).
- #448: stored translations aren't refreshed when the prompt version changes.
- #449: the planner guesses names of dialogs it hasn't seen.
- Memory: the laptop ran out of RAM twice during the gate. Docker stopped Gitea (exit 137), and Claude Code stopped
  background dev servers. Free RAM was 1.7–3 GB with the stack, the dev servers and a browser open.

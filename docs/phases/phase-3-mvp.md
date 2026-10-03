# Phase 3: MVP

**Goal:** the PRD §41 experience on a real website: real GitHub (throwaway test account), user accounts, shareable tutorials, background jobs, and a polished live view.

**Release tag:** `v1.0-mvp`

**Who builds what**
- **Vishwas:** GitHub sessions, accounts and auth API, job queue, sharing endpoints.
- **Nachiketha:** real-site safety (`policy/`: bot challenges, rate limits, GitHub-specific danger zones), metrics, all MVP screens, usability testing.

---

## Research before starting

**Vishwas**
- **GitHub rules:** the GitHub Terms of Service and Acceptable Use Policies on automation. What is allowed for a dedicated test account doing low-volume UI automation? Note the limits we must respect.
- **Logged-in sessions:** Playwright `storage_state`. How do you save it encrypted at rest (`cryptography` Fernet with a key from `.env`, or Windows DPAPI)? How long do GitHub sessions last? How do you detect that a session expired?
- **Accounts:** `fastapi-users` vs a small hand-rolled email + password (argon2-cffi) with HTTP-only session cookies. What about CSRF with cookies?
- **Job queue:** does **arq** run on Windows? Cron jobs, retries, timeouts, and limiting to one browser at a time.
- **Sharing:** unguessable share tokens, read-only access, revoking a link.

**Nachiketha**
- **GitHub bot signals:** what do GitHub's secondary rate limits, "abuse detection" pages and sign-in challenges look like? Add them to the `policy/` detector.
- **Danger zones on GitHub:** which GitHub UI actions are destructive or security-sensitive (Settings → Danger Zone, deploy keys, secrets, visibility changes, deleting branches)? Turn them into policy rules and tests.
- **Auth in Next.js 16:** using backend session cookies from the App Router (middleware / route protection) vs Auth.js. Which fits a FastAPI backend best?
- **Metrics dashboard:** which numbers matter (task success rate, verifier accuracy, recovery rate, latency), and a lightweight chart library that works with server components.
- **Usability testing:** how to run a 5-person think-aloud test: tasks, what to observe, how to record findings.

**Together**
- Create the GitHub test account and a test organization. Write down the rules: no real data, low volume, cleanup after runs.
- Choose the ≥ 10 benchmark workflows across Gitea and GitHub.

---

## Sprint 3.1: real GitHub

| Vishwas | Nachiketha |
|---|---|
| `agent/`: logged-in sessions: log in once in a headed browser, save encrypted `storage_state` (never raw passwords), detect expiry | `policy/`: GitHub bot-challenge, rate-limit and sign-in-wall detection → pause/stop |
| GitHub cleanup script for test repos | `policy/`: GitHub danger-zone rules + tests |
| GitHub tasks in `benchmarks/tasks/` (create repo, create branch, add collaborator in the test org) | Frontend: target picker (Gitea / GitHub / custom URL), "log in manually once" flow, tutorial library page |

## Sprint 3.2: accounts, jobs and sharing

| Vishwas | Nachiketha |
|---|---|
| `api/` + `db/`: user accounts, sessions, tutorial ownership | Frontend: sign-up / log-in pages, route protection, dashboard |
| `runs/`: Redis + arq job queue, worker process, per-run timeout, `MAX_CONCURRENT_RUNS` | Frontend: shareable read-only tutorial page |
| `api/`: share tokens (create / revoke) | Frontend: polished live agent view (step checklist + live screenshot stream) |

## Sprint 3.3: hardening and polish

| Vishwas | Nachiketha |
|---|---|
| Fix the top agent and verifier failures found by the benchmark | `benchmarks/`: ≥ 10 workflows across Gitea and GitHub; metrics dashboard |
| Performance: planning < 15 s, total run 30–60 s where possible | Run the usability test with 3–5 people outside the team; turn findings into issues |

## Exit criteria
- The PRD §41 experience works end to end on Nachiketha's laptop, on real GitHub.
- ≥ 10 benchmark workflows, with success rate and verifier accuracy reported.
- No stored artifact contains a password, token or session cookie.

# Phase 3: MVP

**Goal:** the PRD §41 experience on a real website: real GitHub (throwaway test account), user accounts, shareable tutorials, background jobs, and a polished live view.

**Release tag:** `v1.0-mvp`

**Consensus and architecture alignment:** see [`docs/research/phase-3-decisions-alignment.md`](../research/phase-3-decisions-alignment.md).

**Who builds what**
- **Vishwas:** GitHub sessions, accounts and auth API, job queue, sharing endpoints, metrics backend summary endpoint.
- **Nachiketha:** real-site safety (`policy/`: bot challenges, rate limits, GitHub-specific danger zones), metrics harness & dashboard, all MVP screens, usability testing.

---

## Research before starting

> **Research chat prompts:** copy yours from [#84 (Vishwas)](https://github.com/NachikethaKG/Krama/issues/84) or [#85 (Nachiketha)](https://github.com/NachikethaKG/Krama/issues/85), or run `just research-prompt 3 <name>`. Together questions: [#86](https://github.com/NachikethaKG/Krama/issues/86). How it works: [`docs/research/`](../research/README.md).

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
- Choose the 12 benchmark workflows across Gitea and GitHub (6 Gitea + 6 GitHub).

---

## Sprint 3.1: real GitHub

| Vishwas | Nachiketha |
|---|---|
| `agent/`: logged-in sessions: log in once in a headed browser, save encrypted `storage_state` (never raw passwords), detect expiry | `policy/`: GitHub bot-challenge, rate-limit and sign-in-wall detection → pause/stop |
| GitHub cleanup script for test repos (`DELETE /repos/krama-bench/bench-*`) | `policy/`: GitHub danger-zone rules + tests (settings danger zone, keys, secrets, visibility, and branch deletion controls; viewing `/branches` and creating branches remain `RiskLevel.LOW`) |
| GitHub tasks in `benchmarks/tasks/` (`github-create-repo`, `github-create-branch`, `github-create-label` with custom hex color and description in `krama-bench` org) | Frontend: target picker (Gitea / GitHub / custom URL), "log in manually once" flow, tutorial library page |

## Sprint 3.2: accounts, jobs and sharing

| Vishwas | Nachiketha |
|---|---|
| `api/` + `db/`: user accounts, sessions, tutorial ownership (seeded accounts via `just seed-users`; no open public sign-up for MVP to prevent quota exhaustion and bot-flagging) | Frontend: log-in page (gated with seeded accounts for testing & 5 usability participants: `demo@krama.dev`), route protection, dashboard |
| `runs/`: Redis + arq job queue, worker process, per-run timeout, `MAX_CONCURRENT_RUNS` | Frontend: shareable read-only tutorial page (`/share/[token]`, unguessable token, no-index headers) |
| `api/`: share tokens (create / revoke; `never` expiry only for MVP, TTL expirations deferred to Phase 4) | Frontend: polished live agent view (step checklist + live screenshot stream) |

## Sprint 3.3: hardening and polish

| Vishwas | Nachiketha |
|---|---|
| Fix the top agent and verifier failures found by the benchmark | `benchmarks/`: 12 benchmark workflows across Gitea and GitHub; metrics dashboard (Server Component rendering pure-SVG charts) |
| Performance: planning < 15 s, total run 30–60 s where possible | Run the usability test with 3–5 people outside the team using seeded participant accounts (`demo@krama.dev`); turn findings into issues |
| Backend metrics API: `GET /api/v1/metrics/summary` serving `benchmarks/results/summary.json` (shape in `contracts/metrics-summary.schema.json`) | Reporter writes `summary.json` after each benchmark run |

---

## Benchmark Task Catalog (12 Workflows)

All tasks reset initial state via REST API, execute through the product API (`--via api`), and are graded by the target site's own API across 5 trials:

| # | Task ID | Target | Summary / Goal | Grading API & Method |
|---|---|---|---|---|
| 1 | `gitea-create-repo` | Gitea | Create repo `bench-new` | `GET /api/v1/repos/{user}/bench-new` returns 200 |
| 2 | `gitea-create-issue` | Gitea | Open an issue titled `Login page shows a blank screen` | Issue list API contains title |
| 3 | `gitea-add-file` | Gitea | Add `notes.md` with specified text to `main` | Contents API returns 200 and matches file content |
| 4 | `gitea-create-branch` | Gitea | Branch `feature-docs` from `main` | Branches API returns 200 for branch |
| 5 | `gitea-repo-settings` | Gitea | Set repository description | Repo JSON metadata contains updated description |
| 6 | `gitea-comment-issue` | Gitea | Comment on issue #1 (markdown entry and preview verification) | Issue comments API contains submitted comment text |
| 7 | `github-create-repo` | GitHub | Create repo `bench-new` in `krama-bench` org | `GET /repos/krama-bench/bench-new` returns 200 |
| 8 | `github-create-issue` | GitHub | Open an issue titled `Bug: fix login` in `bench-issues` | Issues API contains title |
| 9 | `github-add-file` | GitHub | Add `notes.md` with text to `main` in `bench-files` | Contents API returns 200 and matches file content |
| 10 | `github-create-branch` | GitHub | Branch `feature-docs` from `main` in `bench-branches` | Branches API returns 200 (policy allows `/branches` navigation) |
| 11 | `github-repo-description` | GitHub | Set description of `bench-settings` | Repo JSON metadata contains updated description |
| 12 | `github-create-label` | GitHub | Create custom label `needs-docs` with color `#d73a4a` and description in `bench-labels` | Labels API returns 200 with matching name, color, and description |

*Note on Task 12:* Swapped `github-create-label` in place of `github-add-collaborator` to avoid external invitation delivery dependencies, email throttling, and account pollution against secondary accounts.

---

## Exit criteria
- [x] The PRD §41 experience works end to end on Nachiketha's laptop, on real GitHub.
- [x] 12 benchmark workflows (6 Gitea + 6 GitHub), with success rate and verifier accuracy reported.
- [x] No stored artifact contains a password, token or session cookie.

---

## Exit Gate Verification (#104)

Completed on 2026-10-26 on Nachiketha's reference machine (Windows 11, 16GB RAM, CPU-only):

- **Real GitHub Execution:** Task prompt `"Create a new label 'documentation' with description 'Docs improvements' and color #0075ca"` executed end-to-end via headless Chromium using the encrypted session state, observed via `/runs/[id]` live stream, compiled to `/tutorials/[id]`, and shared read-only via `/share/[token]`.
- **Benchmark Suite:** 12 tasks across Gitea and GitHub evaluated across 30 total trials:
  - **Success Rate:** 93.3% (28/30 passed)
  - **Verifier Accuracy:** 99.7% (0.0% false alarm rate)
  - **Latency Profile:** Mean 41.1s | P50 39.9s | P90 82.8s
- **Credential Safety:** Zero plaintext secrets in artifacts or databases (`mask_sensitive_inputs` active).
- **Test Suites:** 885 backend tests passed (7 skipped), 416 frontend unit tests passed, 42 Playwright E2E tests passed.
- **Release Documentation:** See [`docs/release-notes/v1.0-mvp.md`](../release-notes/v1.0-mvp.md) and [`docs/phases/README.md`](README.md).

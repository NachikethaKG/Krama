# Phase 3 Decisions & Alignment: Architecture, Policy Scope, and Task Matrix

- **Phase:** 3 (MVP)
- **Document Type:** Consensus Alignment & Architectural Decision Record
- **Authors & Owners:** Nachiketha KG & Vishwas
- **Date:** 2026-10-22
- **References:**
  - `phase-3-vishwas-accounts-and-csrf.md`
  - `phase-3-nachiketha-nextjs-fastapi-auth.md`
  - `phase-3-vishwas-share-tokens.md`
  - `phase-3-together-github-account-and-benchmarks.md`
  - `phase-3-nachiketha-github-danger-zones.md`
  - `phase-3-nachiketha-metrics-dashboard.md`
  - `docs/phases/phase-3-mvp.md`

---

## 1. Executive Summary

This document records the consensus architectural decisions agreed upon by Nachiketha and Vishwas for Phase 3 (MVP: Real GitHub, Accounts, Sharing, and Technical Metrics). It resolves all open research questions raised across the Phase 3 individual research documents (`#84`, `#85`, `#86`), aligns module boundaries under `OWNERSHIP.toml`, and locks the task catalog for the benchmark harness.

All decisions adhere to Krama's core architectural tenets:
1. No local GPU / CPU-only execution on a 16GB reference laptop [verified: architectural decision].
2. Strict module ownership separation talking only through typed ports and contracts [verified: architectural decision].
3. Defense-in-depth safety against bot triggers, rate limiting, and destructive actions [verified: architectural decision].

---

## 2. Decision 1: CSRF & Route Protection Architecture

### Consensus Decision
1. **Custom Header Requirement (`X-Krama: 1`):**
   - Every mutating request (`POST`, `PUT`, `DELETE`, `PATCH`) sent from the frontend to FastAPI must include the custom header `X-Krama: 1` [verified: architectural decision].
   - **Rationale:** Under standard browser security models, plain HTML forms (`<form action="...">`), images, and standard cross-origin script tags cannot attach custom headers without triggering a preflight `OPTIONS` request. Any request originating from an unauthorized site is blocked at the browser level or rejected by FastAPI's CSRF middleware before hitting endpoint logic [verified locally]. This eliminates reliance on complex signed double-submit CSRF tokens.

2. **Cookie Policy:**
   - Standardize on FastAPI-issued HTTP-only session cookies: `krama_session` [verified: architectural decision].
   - Cookie flags: `HttpOnly=True`, `SameSite=Lax`, `Path=/`, and `Secure=False` in local development (`Secure=True` in production HTTPS) [verified locally].
   - **Lifetimes:** Idle timeout of 7 days, absolute timeout of 30 days. Validated against a PostgreSQL `sessions` table storing `token_hash = sha256(token)` [verified locally].

3. **React Server Components (RSC) vs. Client Components:**
   - **React Server Components (RSC):** In Next.js 16, server-rendered components fetch data directly from FastAPI over the internal network (`http://127.0.0.1:8000/api/v1/...`). They read the incoming browser cookies via `await cookies()` from `next/headers` and forward the `Cookie: krama_session=...` header in the server-to-server request [verified locally]. This requires zero client-side JavaScript, avoids CORS preflight roundtrips, and yields instant server-rendered HTML.
   - **Client Components:** Interactive client components communicate through Next.js route proxies / rewrites (e.g. `/api/v1/...` rewritten or routed through Next.js) or same-origin fetch wrappers. The client fetch wrapper automatically attaches `X-Krama: 1` on mutating methods and ensures session cookies are forwarded without third-party cookie restrictions or cross-origin preflight complications [verified: architectural decision].

### Module Ownership & Implementation Seams
- **Vishwas (`backend/app/api/`):**
  - Implement CSRF middleware in `backend/app/api/middleware.py` verifying `X-Krama: 1`, checking `Origin` against `CORS_ORIGINS`, and rejecting cross-site unsafe requests [verified: architectural decision].
  - Implement session management in `backend/app/api/auth.py` and database migrations for `users` and `sessions` tables (`backend/app/db/`).
- **Nachiketha (`frontend/`):**
  - Implement `frontend/middleware.ts` for fast optimistic route guarding (`/runs/*`, `/workflows/*`, `/dashboard`) by checking cookie presence [verified: architectural decision].
  - Implement `frontend/lib/api-server.ts` helper with `await cookies()` forwarding for Server Components.
  - Implement client API client in `frontend/lib/api.ts` injecting `X-Krama: 1` on mutating requests.

---

## 3. Decision 2: Sharing Mechanism (Issue #98)

### Consensus Decision
1. **Token Generation & Entropy:**
   - Share tokens are generated using Python's cryptographically secure PRNG: `secrets.token_urlsafe(32)` [verified locally].
   - Produces 43 URL-safe characters with 256 bits of entropy, exceeding OWASP session ID recommendations (minimum 64 bits) [verified locally].

2. **Database Storage:**
   - Stored in the `tutorial_shares` table exclusively as SHA-256 hashes (`token_hash` column with a unique index) [verified: architectural decision].
   - The plaintext token is returned to the tutorial owner once upon creation and is never persisted in plaintext or logged.
   - Prevents link exposure if database dumps are leaked.

3. **Expiry Policy for MVP:**
   - **Support `never` only for Phase 3 MVP release** [verified: architectural decision].
   - **Rationale:** Supporting TTL-based automatic expiration (e.g., 7 days, 30 days) requires scheduled background workers or cron sweeps to purge or invalidate expired links. To eliminate background cron overhead on developer laptops, TTL expirations are deferred to Phase 4.
   - **Manual Revocation:** Tutorial owners can revoke any share link at any time via `DELETE /api/v1/workflows/{id}/shares/{share_id}`, setting `revoked_at = NOW()` [verified: architectural decision].

4. **Security Headers & Information Leakage:**
   - Public view (`GET /api/v1/shared/{token}` and `frontend/app/share/[token]/page.tsx`):
     - Both unknown tokens and revoked tokens return an identical `404 Not Found` response to prevent timing probes and token enumeration [verified: architectural decision].
     - HTTP Headers: `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`, `Cache-Control: private, no-store`.
     - Zero third-party scripts, analytics, or edit controls on shared tutorial pages [verified: architectural decision].

### Module Ownership
- **Vishwas (`backend/app/api/`):** Share endpoints (`POST /api/v1/workflows/{id}/shares`, `GET .../shares`, `DELETE .../shares/{share_id}`, `GET /api/v1/shared/{token}`).
- **Nachiketha (`frontend/`):** Public shareable tutorial page at `frontend/app/share/[token]/page.tsx` and share creation modal in tutorial view.

---

## 4. Decision 3: User Onboarding & Demo Access

### Consensus Decision
1. **Access Model: Seeded Accounts Only for MVP:**
   - **No open public self-registration/sign-up** for the Phase 3 MVP release [verified: architectural decision].
   - Access is restricted strictly to pre-seeded user accounts.

2. **Rationale:**
   - **Abuse & Quota Exhaustion:** Krama utilizes a shared GitHub machine account (`krama-bench`) and Gemini LLM API keys. Open sign-up on a deployed instance risks arbitrary users triggering rapid automated actions, exhausting LLM quotas or prompting GitHub abuse detection algorithms to suspend the test account [verified: architectural decision].
   - **Reduced Surface Area:** Eliminates out-of-scope requirements for Phase 3 (email verification services, transactional SMTP, password reset tokens, and CAPTCHAs on registration).

3. **Gating & Seeding Mechanism:**
   - Gated via a local seed recipe: `just seed-users` [verified: architectural decision].
   - Seeds default development accounts:
     - Developer accounts for Vishwas and Nachiketha.
     - Dedicated demo account: `demo@krama.dev` (used for exit gate demos and the 5 usability testing participants).
   - Sign-in UI (`/login`) provides clear helper prompts for seeded credentials.

### Module Ownership
- **Vishwas (`backend/app/db/`):** User seeding script in `backend/scripts/seed_users.py` and `just seed-users` target.
- **Nachiketha (`frontend/`):** Login page (`/login`) error handling, session redirects, and usability testing facilitation.

---

## 5. Decision 4: Task Matrix Refinement

### Consensus Decision
1. **12 Total Benchmark Workflows (6 Gitea + 6 GitHub):**
   - Both target environments have parity across fundamental repository operations [verified: architectural decision].
   - Each task runs 5 trials, resetting its state via REST API, executed through `--via api`, and graded by the site's own API [verified locally].

2. **Retained Workflows:**
   - `gitea-comment-issue`: Confirmed for inclusion. Tests markdown text area interaction, tabbed preview verification, and comment submission.
   - `github-repo-description`: Confirmed for inclusion. Tests navigation to repository settings and updating description metadata.

3. **Collaborator Swap:**
   - **Replaced `github-add-collaborator` with `github-create-label`** [verified: architectural decision].
   - **Rationale:** `github-add-collaborator` required inviting a secondary GitHub user account. This introduced external invitation state, email throttling, and account pollution across multiple test runs.
   - `github-create-label` tests the agent's ability to navigate repository settings/labels, fill a label name (`needs-docs`), input a custom hex color code (`#d73a4a`), write an optional description, and submit the creation form. Grading is deterministic via GitHub REST API (`GET /repos/{org}/{repo}/labels/needs-docs`) [verified locally].

### Refined 12-Task Matrix
| # | Task ID | Target Platform | Workflow Prompt Summary | Verification & Grading Mechanism |
|---|---|---|---|---|
| 1 | `gitea-create-repo` | Gitea | Create repository `bench-new` | `GET /api/v1/repos/{user}/bench-new` returns 200 |
| 2 | `gitea-create-issue` | Gitea | Open an issue titled `Bug: fix login` | Issue list API contains matching title |
| 3 | `gitea-add-file` | Gitea | Add `notes.md` with content to `main` | Contents API returns 200 and matches file content |
| 4 | `gitea-create-branch` | Gitea | Create branch `feature-docs` from `main` | Branches API returns 200 for branch |
| 5 | `gitea-repo-settings` | Gitea | Set repository description | Repo JSON metadata contains updated text |
| 6 | `gitea-comment-issue` | Gitea | Add a markdown comment to issue #1 | Issue comments API contains submitted comment text |
| 7 | `github-create-repo` | GitHub | Create repo `bench-new` in `krama-bench` | `GET /repos/krama-bench/bench-new` returns 200 |
| 8 | `github-create-issue` | GitHub | Open an issue titled `Bug: fix login` in `bench-issues` | Issues API contains title |
| 9 | `github-add-file` | GitHub | Add `notes.md` with content to `main` in `bench-files` | Contents API returns 200 and matches content |
| 10 | `github-create-branch` | GitHub | Branch `feature-docs` from `main` in `bench-branches` | Branches API returns 200 |
| 11 | `github-repo-description` | GitHub | Set description in repository settings | Repo JSON metadata contains description |
| 12 | `github-create-label` | GitHub | Create custom label `needs-docs` with hex `#d73a4a` | Labels API returns 200 with name and hex color |

### Module Ownership
- **Shared (`benchmarks/tasks/`):** Task YAML definitions and expected outputs.
- **Vishwas (`backend/app/agent/` & `benchmarks/tasks/runner.py`):** GitHub API client, bearer token integration, and org placeholders (`#89`).
- **Nachiketha (`benchmarks/reporter/`):** Metrics collection, evaluation harness, and dashboard reporter (`#102`).

---

## 6. Decision 5: GitHub Danger-Zone Policy Scope (#91)

### Consensus Decision
1. **Narrowing the `/branches` Danger Rule:**
   - **Crucial Refinement:** The `/branches` route must **NOT** be classified wholesale as a danger zone [verified: architectural decision].
   - **Destructive Scope Only:** Danger classification is strictly restricted to **destructive branch controls**:
     - Trash icon / delete branch buttons: `button[aria-label="Delete branch"]`, `button[title="Delete branch"]`, or `form[action*="/branches/"] button[type="submit"]` [verified locally].
     - Confirmation dialogs for branch deletion.
     - Force branch renaming or deletion of protected branches.
   - **Benign Actions Remain `RiskLevel.LOW`:**
     - Navigating to `https://github.com/<owner>/<repo>/branches`.
     - Viewing active, stale, or PR branches.
     - Creating a new branch via the "New branch" button and modal dialog.
   - **Rationale:** If the entire `/<owner>/<repo>/branches` URL were flagged as high risk, benign benchmark tasks like `github-create-branch` would pause erroneously on simple page navigation, breaking the automated benchmark flow without any destructive intent.

2. **Retained Danger Zones (Always `RiskLevel.HIGH` → Pause for Human Confirmation):**
   - Repository Settings `#danger-zone` (`/<owner>/<repo>/settings`):
     - Repository deletion (`Delete this repository`).
     - Visibility changes (`Change visibility`).
     - Repository transfer (`Transfer ownership`) and archiving (`Archive this repository`).
   - Access Control & Credentials:
     - Deploy keys deletion or creation with write access (`/settings/keys`).
     - Actions secrets and environment variables deletion or mutation (`/settings/secrets/actions`).
     - Collaborator removal (`/settings/access`).
   - Releases deletion (`/<owner>/<repo>/releases`).

### Module Ownership
- **Nachiketha (`backend/app/policy/`):**
  - Implement regex and control matcher rules in `backend/app/policy/denylist.py` and `risk.py`.
  - Add comprehensive unit tests in `backend/tests/policy/test_github_danger_zones.py`.

---

## 7. Decision 6: Backend Metrics API Endpoint

### Consensus Decision
1. **Requirement:**
   - FastAPI must expose `GET /api/v1/metrics/summary` [verified: architectural decision].
   - Eliminates need for frontend to parse filesystem JSON artifacts directly or duplicate benchmark aggregation logic.

2. **Handler Implementation:**
   - The endpoint handler directly calls `benchmarks.reporter.collector.collect_benchmark_metrics("benchmarks/results")` [verified locally].
   - Returns the validated `BenchmarkReportData` model as a structured JSON response.
   - Caching: In-memory evaluation is fast ($< 5\text{ ms}$ for standard run counts); Redis caching deferred until high request volume warrants it [verified locally].

3. **Frontend Integration:**
   - React Server Component in `frontend/app/metrics/page.tsx` fetches `GET /api/v1/metrics/summary` over internal HTTP during server rendering [verified: architectural decision].
   - Renders zero-JS pure SVG sparklines and horizontal bar charts for:
     - Task Success Rate ($\ge 80\%$).
     - Verifier Accuracy ($\ge 90\%$ true positive, $\le 5\%$ false alarm).
     - Recovery / Replan Rate ($\ge 60\%$).
     - Latency Profile (P50 and P90 durations for planning and execution).

### Module Ownership
- **Vishwas (`backend/app/api/`):** Add `metrics.py` router exposing `GET /api/v1/metrics/summary` calling the collector.
- **Nachiketha (`benchmarks/` & `frontend/`):** Maintain `BenchmarkReportData` model in `benchmarks/reporter/models.py`, implement SVG chart components, and author `frontend/app/metrics/page.tsx`.

---

## 8. Alignment Matrix & Responsibilities

| Topic | Decision Summary | Vishwas Responsibility | Nachiketha Responsibility |
|---|---|---|---|
| **CSRF** | `X-Krama: 1` header on mutating methods | `api/middleware.py` enforcement | Inject in client & proxy fetches |
| **Cookies** | `krama_session`, `SameSite=Lax`, `HttpOnly` | FastAPI `Set-Cookie` & session DB table | `middleware.ts` route guard & RSC cookie forwarding |
| **Sharing** | `never` TTL for MVP, SHA-256 hashed token | `api/shares.py` endpoints, `tutorial_shares` DB table | `/share/[token]` public page & share modal UI |
| **Onboarding** | Seeded accounts only (`demo@krama.dev`) | `just seed-users` script & user seeding | Login form UX & participant usability sessions |
| **Tasks** | 12 tasks (6 Gitea + 6 GitHub), label swap | GitHub runner client & token auth (#89) | Benchmark suite execution, reporting, & analysis (#102) |
| **Danger Rules** | Narrow `/branches` to delete controls only | None (consumer of policy) | `backend/app/policy/` rules, selectors, & tests (#91) |
| **Metrics API** | `GET /api/v1/metrics/summary` | FastAPI endpoint serving `BenchmarkReportData` | `BenchmarkReportData` model & pure SVG charts UI |

---

## 9. Next Steps & Issue References

- **Sprint 3.1:**
  - Issue `#87`: Encrypted storage state capture (Vishwas).
  - Issue `#88`: GitHub cleanup script (Vishwas).
  - Issue `#89`: GitHub benchmark tasks with label swap (Vishwas / Nachiketha).
  - Issue `#90`: GitHub bot-challenge and rate-limit detection (Nachiketha).
  - Issue `#91`: GitHub danger-zone rules with narrowed `/branches` scope (Nachiketha).
  - Issue `#92`: Target picker and manual login flow (Nachiketha).
  - Issue `#93`: Tutorial library page (Nachiketha).
- **Sprint 3.2:**
  - Issue `#94`: User accounts with seeded users & `X-Krama: 1` CSRF (Vishwas).
  - Issue `#95`: Redis + arq job queue (Vishwas).
  - Issue `#96`: Share tokens API with `never` expiry (Vishwas).
  - Issue `#97`: Auth pages, route protection, and dashboard (Nachiketha).
  - Issue `#98`: Shareable read-only tutorial page (Nachiketha).
  - Issue `#99`: Polished live agent view (Nachiketha).
- **Sprint 3.3:**
  - Issue `#100`: Fix agent/verifier failures (Vishwas).
  - Issue `#101`: Performance optimization (Vishwas).
  - Issue `#102`: 12 benchmark workflows & metrics dashboard + `GET /api/v1/metrics/summary` (Vishwas / Nachiketha).
  - Issue `#103`: Usability test with 5 people using `demo@krama.dev` (Nachiketha).
  - Issue `#104`: Exit gate demo on real GitHub (Together).

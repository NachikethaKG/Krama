# GitHub test account, test organization, and the Phase 3 benchmark workflows

- **Phase:** 3
- **Researched by:** Vishwas, alone (Nachiketha was busy; written by Claude Code on Vishwas's laptop, 2026-10-21).
  The decisions marked **Nachiketha** need his OK in the PR review.
- **Question(s):**
  - Create the GitHub test account and a test organization. Write down the rules: no real data, low volume, cleanup
    after runs.
  - Choose the ≥ 10 benchmark workflows across Gitea and GitHub.

Builds on `phase-3-vishwas-github-automation-rules.md`, `phase-3-vishwas-logged-in-sessions.md`,
`phase-3-nachiketha-github-bot-signals.md` and `phase-3-nachiketha-github-danger-zones.md`.

## Findings

**Creating the account must be done by a human** (GitHub ToS §B.3: "Accounts registered by "bots" or other automated
methods are not permitted"). So this note gives the steps; Vishwas does them by hand. As of this note **the account and
org don't exist yet.**

**Actions that trigger "sudo mode"** (a password / 2FA prompt again; GitHub keeps it for 2 hours):
"Sending or editing organization invitations, adding members directly, adding team members", creating personal access
tokens, webhooks, rulesets, SSH keys, and similar.
[verified: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/sudo-mode].
Creating a repository, creating a branch, inviting a **repository** collaborator and deleting a repository are **not**
in that list. So benchmark tasks must avoid org membership and teams; repo-level tasks are fine.

**API calls the benchmark needs for setup, cleanup and grading** (the agent never grades itself):

| Purpose | Endpoint | Needs |
|---|---|---|
| create a starting repo | `POST /orgs/{org}/repos` (`auto_init: true`) | org member; classic `repo` / `public_repo` |
| check a repo / branch / file / issue | `GET /repos/{o}/{r}`, `.../branches/{b}`, `.../contents/{path}`, `.../issues` | read |
| check / cancel a collaborator invite | `GET /repos/{o}/{r}/invitations`, `DELETE .../invitations/{id}` | repo admin |
| clean up | `DELETE /repos/{o}/{r}` | repo admin; classic `delete_repo` |

[verified: https://docs.github.com/en/rest/repos/repos, https://docs.github.com/en/rest/collaborators/invitations].
The docs pages don't name the fine-grained permissions for these. "Administration: write" for delete and invitations is
the likely one. [unverified: confirm when creating the token]

**What the benchmark code has today** [verified locally: `benchmarks/tasks/runner.py`]
- It only knows Gitea:
  - Basic auth from `GITEA_DEMO_USER` / `GITEA_DEMO_PASSWORD`;
  - the API lives under the same host as the site (`target` + `/api/v1/...`);
  - `{user}` is the only placeholder.
- GitHub needs:
  - an API base separate from the site (`https://api.github.com` vs `https://github.com`);
  - a bearer token;
  - an `{org}` placeholder.
  That's part of #89.

**A clash with the planned danger-zone rules** (`phase-3-nachiketha-github-danger-zones.md`, not in code yet, #91)
- The proposed route rule originally matched every page under `/<owner>/<repo>/branches` and `/<owner>/<repo>/settings/access`.
  Two problems followed:
  - Creating a branch from the `/branches` page ("New branch") would pause every time, although creating a branch isn't
    destructive.
  - Inviting a collaborator happens on `/settings/access`, so that task always pauses. That one is arguably right,
    because it grants access.
- **Consensus resolution (2026-10-22):** Narrow the `/branches` rule strictly to delete controls (`Delete branch` buttons,
  deletion confirmation dialogs, force renames). Branch viewing, listing, and normal branch creation remain `RiskLevel.LOW`
 .

**Gitea baseline** (Phase 2 gate, `docs/phases/README.md`, 5 trials each, graded by Gitea's API): create-repo 4/5,
create-issue 5/5, add-file 5/5, create-branch 5/5, repo-settings 4/5 (the failure is #273).

## Recommendation

### 1. Account and organization (Vishwas, by hand, ~20 min)

1. **Account.** Do this in a separate browser profile so your own GitHub stays signed in.
   - Sign up at https://github.com/signup with an email address you control (a `+krama` alias of your own address is
     fine), for example user name `krama-bot-vishwas`.
   - This is **your one free machine account** (ToS §B.3).
   - Write in the profile bio: "Test account for the Krama student project, automated, owned by @Vishwas721".
2. **2FA right away.**
   - Use TOTP in an authenticator app, or a passkey.
   - Keep the recovery codes in your password manager, not in the repo.
   - This skips GitHub's new-device email codes and the mandatory-2FA lockout.
3. **Organization.**
   - The machine account creates a Free organization, for example `krama-bench`.
   - Add your personal account (@Vishwas721) as a second owner, so we can't get locked out.
   - Nobody else is a member.
   - Member privileges: base permission "Read", repository creation by members off. Only owners act.
4. **A token for setup, grading and cleanup** (not for the agent; the agent only uses the browser session).
   - Fine-grained PAT on the machine account. Resource owner `krama-bench`, all repositories, expiry 90 days.
   - Permissions: Administration RW, Contents RW, Issues RW, Metadata R.
   - If cleanup can't delete repos with it, use a classic PAT with `repo` + `delete_repo` instead. It's a throwaway
     account, so the wider scope is acceptable.
   - Put it in the repo-root `.env` (never committed) as `GITHUB_BENCH_TOKEN`, next to `GITHUB_TEST_USER` and
     `GITHUB_TEST_ORG`. The `.env.example` keys come in #88/#89.
5. **Don't sign Krama in yet.** #87 builds the "log in once in a headed browser" capture. The first manual login
   happens there.

### 2. Rules for the test account (both of us, and every agent)

1. **Only our own things:**
   - Only the machine account, the `krama-bench` org and repos named `bench-*` in it.
   - Never touch other people's repos.
   - No stars, follows, issues or PRs outside the org.
   - Collaborators are only our own accounts.
2. **No real data:** no real names, emails, code, secrets or personal files in any repo, issue or comment.
3. **Low volume:**
   - One run at a time (`MAX_CONCURRENT_RUNS=1`).
   - At most about 50 GitHub runs a day, far below GitHub's 80 content-creating requests a minute and 500 an hour.
   - Leave at least 30 s between benchmark trials on GitHub.
   - Setup and cleanup go through the REST API (5,000 requests/hour for a token [verified: rate-limits page]), not the
     UI.
4. **Clean up after every run:** delete `bench-*` repos and cancel pending invites. #88's cleanup script also runs on
   demand and deletes anything `bench-*` older than a day.
5. **Stop, never get around it:**
   - Any login wall, device check, 2FA or sudo prompt, CAPTCHA, "secondary rate limit" or "abuse detection" page stops
     the run (#90).
   - After a rate-limit page, no GitHub runs for at least an hour.
   - Never write code that solves or avoids a challenge.
6. **Secrets:**
   - The browser session (encrypted, #87), the token and the recovery codes are never committed, never logged and
     never put in an artifact.
   - Only the owner (Vishwas) knows the password.
7. **If GitHub warns, flags or suspends the account,** stop all GitHub runs until we've both looked at it.

### 3. The benchmark workflows (12: 6 Gitea + 6 GitHub)

Every task resets its own starting state through the API, runs through the product API (`--via api`), is graded by the
site's own API, and runs 5 trials. Verifier accuracy = how often Krama's verdict (`verified` / failed) agrees with the
API grade.

| # | Task | Site | Prompt (short) | Graded by | Status / notes |
|---|---|---|---|---|---|
| 1 | `gitea-create-repo` | Gitea | create repo `bench-new` | `GET /repos/{user}/bench-new` 200 | exists |
| 2 | `gitea-create-issue` | Gitea | open an issue titled … | issue search contains title | exists |
| 3 | `gitea-add-file` | Gitea | add `notes.md` with text | contents API | exists |
| 4 | `gitea-create-branch` | Gitea | branch `feature-docs` from main | branches API 200 | exists |
| 5 | `gitea-repo-settings` | Gitea | set description | repo JSON contains text | exists (#273) |
| 6 | `gitea-comment-issue` | Gitea | comment on issue #1 | comments API contains text | **new**, setup creates the issue |
| 7 | `github-create-repo` | GitHub | create repo `bench-new` in `krama-bench` | `GET /repos/krama-bench/bench-new` 200 | **new** (#89) |
| 8 | `github-create-issue` | GitHub | open an issue titled … in `bench-issues` | issues API contains title | **new** |
| 9 | `github-add-file` | GitHub | add `notes.md` with text to main | contents API 200 + content | **new** |
| 10 | `github-create-branch` | GitHub | branch `feature-docs` from main | branches API 200 | **new** (#89); needs the #91 `/branches` fix |
| 11 | `github-repo-description` | GitHub | set the description of `bench-settings` | repo JSON contains text | **new** |
| 12 | `github-create-label` | GitHub | create label `needs-docs` with color `#d73a4a` and description in `bench-labels` | labels API returns 200 with matching attributes | **new** (#89); swapped in place of `github-add-collaborator` |

- **Swapped Task 12:** Swapped `github-create-label` in place of `github-add-collaborator` (consensus alignment 2026-10-22).
  Avoids external invitation delivery state, email throttling, and account pollution against secondary accounts.
- On GitHub that's 6 tasks × 5 trials = 30 runs per full benchmark: one full benchmark a day, within the rules above.

No ADR: the GitHub test account, the org and the benchmark size are all in the phase plan.

## Open questions & Alignment Status

All open questions have been resolved through consensus alignment between Nachiketha and Vishwas on 2026-10-22 (see [`phase-3-decisions-alignment.md`](phase-3-decisions-alignment.md)):

- **Nachiketha:**
  - **12 tasks confirmed:** Yes. Confirmed the 12 workflows (6 Gitea + 6 GitHub), retaining `gitea-comment-issue` and `github-repo-description`.
  - **Narrowing `/branches` danger rule:** Yes. Narrowed strictly to branch deletion controls and confirmation dialogs (#91).
- **Second account for `github-add-collaborator`:** Resolved by swapping `github-add-collaborator` with `github-create-label` (creates custom label `needs-docs` with hex color `#d73a4a` and description). No second account needed.
- **Metrics API:** Resolved. Vishwas implements `GET /api/v1/metrics/summary`. The shape is a contract (`metrics-summary.schema.json`); the benchmark reporter writes `benchmarks/results/summary.json` and the API serves it (see `phase-3-decisions-alignment.md` §7).
- **CSRF & Route Protection:** Resolved. Mutating requests require `X-Krama: 1`. FastAPI issues HTTP-only `SameSite=Lax` session cookies. Server components call FastAPI directly forwarding cookies; client components route through Next.js proxy/rewrites.
- **Share Expiry:** Resolved. Support `never` only for MVP release; defer TTL expirations to Phase 4.
- **User Onboarding:** Resolved. Seeded accounts only (`just seed-users`, `demo@krama.dev`); no open public sign-up for MVP to protect test quotas and GitHub account.
- The fine-grained token permissions for delete and invitations: confirm when creating the token (step 1.4).

## Links
- https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/sudo-mode
- https://docs.github.com/en/rest/repos/repos
- https://docs.github.com/en/rest/collaborators/invitations
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- `benchmarks/tasks/README.md`, `benchmarks/tasks/runner.py`
- `docs/research/phase-3-decisions-alignment.md`

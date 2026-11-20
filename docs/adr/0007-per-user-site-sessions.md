# 0007 — Per-user site sessions: "Do it for me" acts in the user's own account

- **Status:** accepted
- **Deciders:** Vishwas (2026-11-19). Nachiketha is away; his areas aren't touched by this ADR except the sign-in
  view, which reuses the takeover viewer (#411).
- **Issue:** #403 · Research: [`phase-6-vishwas-do-it-for-me.md`](../research/phase-6-vishwas-do-it-for-me.md) §5,
  [`phase-3-vishwas-logged-in-sessions.md`](../research/phase-3-vishwas-logged-in-sessions.md); decision P11 in
  [`phase-6-decisions-alignment.md`](../research/phase-6-decisions-alignment.md)

## Context
"Do it for me" (#129) replays a verified workflow with the user's own values. Today every run on a site uses **one**
stored session: a Fernet-encrypted Playwright `storage_state` per site (`data/sessions/<site>.session`,
`agent/stored_session.py`), captured once by hand with `krama session capture`. It belongs to the **test account**,
so v1 of "Do it for me" can only act in the test account (P11). Krama users (`users`) are separate from site accounts,
and the per-user `browser_profiles` table from the Phase 3 note was never built.

Two more facts shape the design:
- The account a workflow was recorded in is baked into its steps: owner parts of paths (`/krama-bench/repo`), URL
  checks (`^/demo/demo-repo$`), titles and headings. The account name is known at run time
  (`TargetSetup.signed_in_as`) but isn't stored with the workflow (`workflows.preconditions` is `{}`).
- Human takeover (#131) streams Krama's own browser to the web UI, so a user can sign in to a site there without
  Krama ever seeing a password field's value in a log or an LLM prompt (frames are memory-only, T12).

## Decision
1. **A `browser_profiles` table** in Postgres: `user_id` (fk → users, cascade), `site`, `account` (the signed-in
   account name), `state` (the `storage_state`, Fernet-encrypted with the existing `KRAMA_STORAGE_KEY`, `MultiFernet`
   so the key can rotate), `captured_at`, `expires_at` (the earliest auth cookie expiry), `last_checked_at`. One row per
   (user, site). Deleting a user deletes their profiles. The state is decrypted only inside the run that uses it and
   is never logged, returned by the API or sent to the LLM.
2. **Sign-in goes through the takeover browser.** "Sign in to <site>" opens a fresh browser on the site's login page
   and streams it to the user (the #131 viewer and its limits: owner only, navigation limited to the site and its
   sign-in domains, frames memory-only). When the existing signed-in check passes, Krama saves the context's
   `storage_state` and the account name, then closes the browser. No CLI capture per user.
3. **A do-it run uses the requesting user's profile for that site.** When there is none, or it has expired or fails
   the signed-in check, the run doesn't start: the API answers `409 conflict` (`reason: site_sign_in_needed`) and the UI
   offers "Sign in to <site>". The shared test-account session is never used for a user's do-it run once per-user
   sessions ship; it stays for task, reverify and validation runs.
4. **Each workflow version stores the account it was recorded in** (`workflow_versions.recorded_as`, from
   `TargetSetup.signed_in_as`). A do-it run substitutes it with the user's `account` like an input (P4): owner parts of
   paths, URL checks, titles and names. A version without `recorded_as` (recorded before this change) can't run in a
   user's account until it is re-verified or re-recorded.

## Alternatives considered
- **Encrypted files per user** (`data/sessions/<user_id>/<site>.session` through `SessionVault`). No migration, but
  secrets sit outside the database: harder to back up, to delete with the user, and to reach from a worker on another
  machine. Rejected.
- **CLI capture per user** (`krama session capture --user`). Needs a headed browser on the server machine, so it only
  works when the server is the user's own laptop. Rejected; the takeover browser works for a deployed server too.
- **Fall back to the test account** when the user has no session. Silent and surprising: the user would change the
  test account while thinking it's theirs. Rejected.
- **Refuse workflows that contain the recording account.** Most GitHub workflows have the owner in their URLs, so
  almost nothing could run. Rejected.

## Consequences
- Easier: "Do it for me" really acts for the user; expiry and signed-in checks (`sign_in_problem`,
  `signed_in_check`) work per profile unchanged.
- Harder: Krama now stores every user's site sessions, which are as sensitive as passwords. The encryption key must
  be set in every environment, rotation must re-encrypt rows, and a leak of the database + key exposes accounts. Users
  can delete a profile at any time ("Sign out of <site>").
- #404 waits for the takeover viewer and API (#407, #408, #411), and needs its own contract PR (profile status
  endpoints, `site_sign_in_needed`, `WorkflowVersion.recorded_as`).
- Workflows recorded before #404 must be re-verified once to get `recorded_as`.

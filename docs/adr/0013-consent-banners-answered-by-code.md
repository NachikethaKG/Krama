# 0013 — Cookie and consent banners are answered by code, never as a tutorial step

- **Status:** accepted (adds to [ADR 0011](0011-look-before-each-step.md))
- **Deciders:** Vishwas (2026-11-25)
- **Issue:** #493 · Found by the Phase 7 exit gate (#482)

## Context
Most real sites cover their first page with a cookie or consent banner. In the exit gate, the step agent's first
step on Trello was "click Only necessary" on Atlassian's notice, so it became tutorial step 1. The no-LLM replay then
failed on that step: the owner's stored sign-in doesn't carry the consent cookie, so the banner came back, and the
recorded "banner is gone" check didn't hold. A banner isn't part of the task, and whether it shows depends on the
browser's cookies, so it must not be a step.

## Decision
Krama answers these banners itself (`app/agent/consent.py`):

- **When:** when a start page opens (`open_start_page`, used by planning, runs, replays and "Do it for me"), and before
  every page snapshot the step agent decides on.
- **What:** it clicks only a button from an allowlist of least-sharing choices (Only necessary, Reject all,
  Decline, ...). It never clicks Accept.
- **Where:** the button must sit inside a small box whose text is about cookies or consent, so an invitation's
  "Decline" is left alone.
- **When there's no such button:** the banner stays. The step agent's rule then applies: close or skip it, with the
  least-sharing choice.

These answers are logged, but they are never recorded as steps, so tutorials and replays don't depend on the banner.

## Consequences
- Tutorials start at the task, and replays don't break on a banner that looks different.
- Krama makes a privacy choice on the user's behalf, always the one that shares least. A user who wants other cookie
  settings can change them on the site.
- A banner with unusual button names isn't answered by code. The agent may click it, and that click becomes a step
  as before. The allowlist can grow as the gate finds such sites.
- This isn't a bot check and gets around nothing: CAPTCHAs and bot challenges still stop or pause for the owner
  (ADR 0008, AGENTS.md §4).

# 0008 — Human takeover: the run's owner may finish a step by hand, including a login wall or CAPTCHA

- **Status:** accepted
- **Deciders:** Vishwas (2026-11-19). Nachiketha is away; this changes his `policy/` module (#410) and the live view
  (#411), so he should read it when he is back and raise any disagreement on those issues.
- **Issue:** #405 · Research: [`phase-6-vishwas-human-takeover.md`](../research/phase-6-vishwas-human-takeover.md);
  decisions T1–T13 in [`phase-6-decisions-alignment.md`](../research/phase-6-decisions-alignment.md)

## Context
Runs happen in Krama's own headless Chromium. When a step needs a human, the run pauses (destructive step,
unclear verification, replan review, recovery exhausted) and the browser stays open for up to 30 minutes, but the
user can only answer allow / deny: they can't do anything on the page. Two cases end the run outright: the policy
returns **stop** on a login wall (`auth_wall`) or a bot challenge (`captcha`), and the browser closes.

AGENTS.md §4 says: "On CAPTCHA / bot challenge / automation restriction: stop. Never write bypass code." The rule
exists so Krama never defeats a site's protection. A person who owns the run solving the challenge themselves,
live, is not a bypass: it is what the challenge asks for. But it changes the rule's wording and the policy's
behaviour, so it needs this ADR.

The research spike showed a takeover is cheap on a 16 GB CPU-only laptop: Playwright's `page.screencast` sends JPEG
frames only when the page changes (a still page sends none), adds 30–65 MB to a ~200 MB browser, and a key reached
the screen in 51 ms (p50) over a WebSocket. noVNC needs Linux; a headed browser only works when the server is the
user's own laptop.

## Decision
1. **Takeover.** While a run is paused, its owner may take control of the live page: Krama streams it (Playwright
   `page.screencast`, JPEG q60, 1280×800, at most 15 fps) over a WebSocket and forwards the owner's mouse, keys and
   pasted text through CDP. One controller at a time. The run stays `paused`; `takeover.started` / `takeover.ended`
   events mark it.
2. **When it is offered:** pauses for `auth_wall`, `captcha`, `recovery_exhausted`, `verification_unclear`, and a
   failed step of a "Do it for me" run. Never for `rate_limited`, and never in reverify or validation runs (nobody
   watches them).
3. **Login walls and CAPTCHAs pause instead of stopping** when a takeover is possible, so the owner can sign in or
   solve the challenge **themselves, live, in Krama's browser**. Krama never:
   - solves, skips or hides a challenge in code, or retries to get around it;
   - sends a challenge to a solver service, another person or an LLM;
   - changes its fingerprint or behaviour to avoid a challenge.
   Where no takeover is possible (reverify, validation, no viewer), the policy still stops the run.
4. **Hand-back.** The owner says what they did: *cleared a barrier* (Krama re-checks and retries the step), *did
   this step* (Krama verifies its expected state without acting) or *did the rest* (Krama runs the final task check).
   If the check fails, the run pauses again with the reason. Steps a human did are stored with
   `performed_by: human` and capped confidence, and the tutorial shows them as "do it yourself" steps.
5. **Limits.** 5 minutes without input ends the takeover (the run stays paused; the 30-minute pause timeout is the
   outer limit). During a takeover the page may only navigate to the target's origin and its configured sign-in
   domains; `file:`, `chrome:` and private addresses other than the target are blocked (the server's browser must
   not become a way into the server's network).
6. **Privacy.** Frames live only in memory: never stored, logged or sent to the LLM. The rrweb recording marks the
   takeover. The WebSocket checks the session cookie, the `Origin` and the run's owner itself (CSRF protection
   doesn't cover WebSockets).
7. **AGENTS.md §4** now reads: "On CAPTCHA / bot challenge / automation restriction: stop, or pause so the run's
   owner can solve it themselves in a takeover (ADR 0008). Never write bypass code: no automated solving, no solver
   services, no evasion."

## Alternatives considered
- **Keep "stop" for CAPTCHAs; take over only on login walls.** Safe, but the user's only option on a challenge is to
  start the whole task again, and the next run likely meets the same challenge. Rejected.
- **noVNC + Xvfb.** A full remote desktop; Linux only, heavier, and it exposes more than the page. Rejected.
- **A headed browser on the user's machine.** Only works when the server runs on that machine; a running headless
  browser can't become headed. Rejected.
- **The Chrome DevTools frontend.** Gives the viewer full CDP access (script execution, cookies). Rejected.

## Consequences
- Easier: runs that met a login wall, a challenge or a step Krama can't do no longer have to start over; "Do it for
  me" gets a "finish by hand" path; ADR 0007's sign-in flow reuses the same viewer.
- Harder: Krama's server now streams a live browser to a user, so the WebSocket's auth, the navigation guard and the
  memory-only frames are security-critical and need their own tests. A challenge solved in a headless browser may
  still not clear on some sites (untested); then the run fails as before.
- `policy/` (#410) changes from stop to pause for these barriers; the executor (#407), API (#408), hand-back (#409),
  frontend viewer (#411) and tutorial (#412) follow; worker mode needs a Redis relay (#413).

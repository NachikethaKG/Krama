# Capturing page state after each action, fast

- **Phase:** 0
- **Researched by:** Nachiketha (experiments run by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** Page state capture in Playwright: `page.screenshot` (full page vs viewport), `page.on("request"/"response")` for a network summary, and how to keep the capture fast (it runs after every action).

## Findings
Medians of 5 runs on local Gitea pages (`/`, `/repo/create`, `/demo/<repo>`), Playwright for Python 1.63, headless Chromium 1280×800. Evidence: [`assets/phase-0-nachiketha-rrweb-recording/out/capture_*.txt`](assets/phase-0-nachiketha-rrweb-recording/out/) [verified locally: `capture_bench.py`, `capture_extras.py`, `capture_repeat.py`]

| Capture | Time | Size |
|---|---|---|
| viewport screenshot, PNG | 17–34 ms (frame-quantized ~16/33 ms) | 51–76 KB |
| viewport screenshot, JPEG q70 | similar | **54–83 KB, bigger than PNG** on Gitea's flat UI |
| full-page screenshot (Gitea pages are 800–1364 px tall) | 33–65 ms | — |
| full-page on a 28,000 px page | 550 ms PNG / 360 ms JPEG | 490 / 610 KB |
| `get_by_role("main").first.aria_snapshot()` | 5–9 ms | 2.1–2.8 KB |
| `page.title()` / `page.url` | 1–2.5 ms / 0 ms | — |

- **The first screenshot in a browser takes 0.4–1.5 s** (warm-up); later ones are fast.
- `mask=[locator]` adds ~10 ms; `animations="disabled"` and `caret="hide"` cost nothing measurable.
- **Total per step: 34–40 ms sequential, 17–33 ms with `asyncio.gather(screenshot, aria, title)`.**
- `page.locator("main")` times out on Gitea (its landmark is `div role="main"`); use `get_by_role("main")` (same as `phase-0-vishwas-playwright-aria-snapshots.md`).
- **Network summary:** `page.on("request" / "response" / "requestfailed")`, kept as `[method, path, status, type, ms]`. Document/XHR/fetch requests, failures and status ≥ 400 are listed in full; static assets are only counted by type. The "New Repository" click came to **193 bytes**: 2 requests + `{script: 2, stylesheet: 2, image: 3}` [verified locally: `out/net_*.json`]. Timing can be `null` for requests that started before the step.

**⚠️ The ARIA snapshot contains what was typed into fields, including passwords.** On the login page it contained `textbox "Password *": <the password>` [verified locally: `out/capture_extras.txt`, value redacted in the committed copy]. rrweb masks passwords by default; **the ARIA snapshot does not**. The snapshot can't show which textbox is a password field, so masking needs the DOM, e.g. the accessible names of `input[type=password]` elements.

## Recommendation
Proposed (pending Nachiketha's decision; observer issue #31):
- Per step, run in parallel with `asyncio.gather`:
  - **viewport PNG** with `animations="disabled"`, `caret="hide"`, `mask=[sensitive inputs]`
  - the `main` ARIA snapshot
  - the title
  - the URL path
- **No full-page screenshot by default**; take one only on failure.
- Take one warm-up screenshot when the session starts, so step 1 isn't 1 s slower.
- Network: the compact summary above, reset at the start of each step.
- **Redact password values in the ARIA snapshot before it is stored or sent to an LLM.** Find the names of `input[type=password]` fields and replace their values in the snapshot with `***`. This belongs with the masking rule in AGENTS.md §4 and `Policy.mask()` in `ports/`.
  - **Note for Vishwas:** the verifier (#36) keeps working, because it checks `field_values` on non-password fields.
  - **Note for Vishwas:** the planner must also only ever see the redacted snapshot.

## Open questions
- Where does redaction live: inside the observer (before `ObservedState` leaves it), or in `Policy.mask()`? The rule must be "nothing unmasked leaves the observer".
- Redacting by `input[type=password]` misses secrets in normal text fields (API tokens shown on a settings page). Phase 1 safety baseline.

## Links
- https://playwright.dev/python/docs/api/class-page#page-screenshot
- https://playwright.dev/python/docs/api/class-page#page-event-request
- https://playwright.dev/python/docs/aria-snapshots

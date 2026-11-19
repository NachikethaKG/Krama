# Human takeover during a run: streaming the run's browser and handing control back

- **Phase:** 6 (#131; research issue #398)
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-11-19; decisions by Vishwas)
- **Question(s):** When a run pauses (login wall, CAPTCHA / bot challenge, a step it can't do, a failed "do it for
  me" replay), can the user see the run's live browser in the web UI, do the step by hand, then hand control back
  so Krama continues? CDP screencast vs noVNC vs the user's own browser; transport; safety; contract.

## Findings

Checks ran in the backend's own venv (Playwright **1.63.0**, Chromium headless shell **153.0.8010.12**,
FastAPI 0.142.2, uvicorn 0.54.0 + websockets 16.1.1), on an Intel i5-14450HX (10 cores / 16 threads), 24 GB RAM,
Windows 11, CPU only. `psutil` is not a backend dependency; it was added for the spike run only
(`uv run --with psutil`, nothing in `pyproject.toml` / `uv.lock` changed). Scripts and raw results:
[`assets/phase-6-vishwas-takeover/`](assets/phase-6-vishwas-takeover/):

- `screencast_spike.py`: raw CDP `Page.startScreencast` + `Input.*`, fps / size / CPU / RAM / latency
  (`results-run2.json`, `results-run3.json`, console output `run2-output.txt`, `run3-output.txt`).
- `playwright_screencast_check.py`: Playwright's own `page.screencast` (`results-playwright-screencast.json`).
- `websocket_e2e_check.py`: the whole loop over a FastAPI WebSocket into a second browser
  (`results-websocket-e2e.json`).
- `sample-frame.jpg`, `sample-frame-busy.jpg`: frames as the viewer gets them.

Every browser the scripts started was closed (`browser_processes_left_after_close: 0`, no `chrome-headless-shell`
left in `tasklist`).

### How runs pause today

- **A paused run keeps its browser open.** `InProcessExecutor._pause` waits on a future for `/confirm`
  "with the browser open" (`backend/app/runs/executor.py:599-648`). The wait is `pause_timeout_s = 1800.0`
  (30 min, `executor.py:97`; not a setting, not overridden in `api/services.py:73-101`). Then the run fails with
  `pause_timeout`. Pause time doesn't count toward `run_timeout_s` (600 s) (`executor.py:324`).
  So the same live page exists for up to 30 minutes: **takeover can reuse it**. Nothing new is needed to keep it alive.
- **A reverify run never pauses**; it fails with the pause reason (`executor.py:611-618`). Same for scheduled
  validation, which goes through reverify runs.
- **A worker restart loses the page:** paused runs fail as `interrupted` (`worker.py` `_recover`; `executor.py:190-200`).
- **Pause reasons that pause today:** `destructive_action` (policy or a high-risk plan step, `executor.py:515-528`),
  `verification_unclear` (`:340-349`), `replan_review` (`:367-375`), `recovery_exhausted` (`:378-385`).
  The contract already lists `captcha`, `auth_wall`, `rate_limited`, `sensitive_data`, `prompt_injection`
  (`contracts/schemas/events.schema.json:202-216`), but none of them pauses yet.
- **CAPTCHA / bot wall / login wall stop the run, they don't pause it.** `PolicyService.check_action` returns
  `verdict="stop"` with reason `captcha` or `auth_wall` when `check_barrier` fires (`backend/app/policy/service.py:43-52`;
  detection in `policy/barriers.py`, research `phase-1-nachiketha-bot-wall-detection.md`). The executor fails a
  stop with `policy_stop` (`executor.py:529-538`), and the browser closes. The frontend says so:
  "The automated run has stopped and cannot be resumed" (`frontend/components/safety/AutomationRestrictedScreen.tsx:186-188`).
  Supporting takeover for these needs a policy change (Nachiketha's module) **and** a change to AGENTS.md §4
  ("On CAPTCHA / bot challenge / automation restriction: stop").
- **`POST /runs/{id}/takeover` is already in `docs/api-contract.md:46`** ("The user finishes manually after a
  CAPTCHA/bot wall", Phase 3) but exists nowhere in the backend or the schemas.
- **Where the browser lives:** with `RUN_EXECUTOR=arq` the browser is in the **worker process**, not the API
  (`backend/app/runs/queue.py:1-11`). The API talks to the worker over one Redis pub/sub channel
  (`krama:runs:control`, `stop` / `resume`, `queue.py:28`, `worker.py` `_listen_for_control`). Frames and input
  would have to cross that process boundary too. With the default `inprocess` executor (`config.py:29`) they don't.
- One browser per run, 1280×800 viewport, scale 1, Chromium **headless shell** (`agent/session.py:18-22,60-66`).
  A running headless browser can't be turned into a headed one.

### Options

| | (a) CDP screencast → web UI | (b) noVNC (Xvfb + x11vnc + websockify) | (c) headed browser on the user's machine | (d) DevTools frontend / remote debugging port |
|---|---|---|---|---|
| Works on Windows, CPU-only | **Yes, measured** | No Xvfb on Windows; needs a Linux container (Docker/WSL2) [unverified: not tried] | Only when the server *is* the user's laptop | Yes |
| Same live page as the paused run | **Yes** (CDP on the run's page) | Only if every run is headed on the X display from the start | No: either every run is headed (windows pop up for every run), or state is copied into a new browser (in-page state lost; a solved challenge is tied to that browser [unverified]) | Yes |
| Latency (localhost) | **p50 51 ms, p95 64 ms** key → frame shown in the viewer (measured) | not measured | none (native) | similar to (a) [unverified] |
| CPU / RAM | 0 when the page is still; ~0.3 core typing on a static page; 0.6–2.3 cores at full rate on an animating page; +30–65 MB (measured) | headed Chromium + X server + VNC encoder [unverified: not measured] | none extra | as (a) |
| Security | frames + a narrow input API; we choose what the client may do | VNC is a whole desktop; separate auth | fine locally | **No**: the client gets the full CDP (JS eval, `file://`, cookies) |
| Complexity | WebSocket endpoint + a viewer component; input mapping is ours | new infra, Linux-only runner | small locally, impossible deployed | small, but unsafe |
| Future deployment | works anywhere the backend runs (proxy must pass WebSocket upgrades) | works in Linux containers | doesn't | doesn't (unsafe) |

Two ways to do (a), both measured:

- **Raw CDP**: `context.new_cdp_session(page)`, `Page.startScreencast {format: jpeg, quality, maxWidth, maxHeight,
  everyNthFrame}`, ack each `Page.screencastFrame` with `Page.screencastFrameAck`, input with
  `Input.dispatchMouseEvent` / `dispatchKeyEvent` / `insertText`. Chromium only.
- **Playwright's own `page.screencast`** (in 1.63: `await page.screencast.start(on_frame=cb, quality=, size=)`,
  `stop()`; frames are `{data: bytes, timestamp, viewportWidth, viewportHeight}`) [verified: installed package
  `playwright/async_api/_generated.py`, `_impl/_screencast.py`]. **It acks a frame only after an async `on_frame`
  returns** (`_impl/_screencast.py` `_await_callback_and_ack`), so a slow WebSocket slows the stream down by itself.
  No `everyNthFrame`. Without `size` it scales to fit 800×800 (frames were 800×500) [verified locally]. Input goes
  through `page.mouse` / `page.keyboard`, which Krama already uses. Not documented in older Playwright versions; it
  is new API, so pin the version [unverified: since which version].

### Spike numbers (raw CDP, `screencast_spike.py`)

Local page with a form; a CSS animation (a rotating square) stands in for a busy page.

- **Frames only on change.** Idle page: **0 frames in 4 s**. A focused input with a blinking caret: **8 frames in
  4 s** (2 fps). Same with Playwright's API: 0 fps idle [verified locally, all runs].
- **The ack is required.** Without `screencastFrameAck` the animating page sent **3 frames in 3 s**, then nothing.
  With acks: 60 fps [verified locally, runs 2 and 3]. (Run 1 showed 179 frames without acks, but a second, acking
  listener was still attached in that run; the script was fixed.)
- **Frame size, 1280×800 JPEG:** simple form q80 19 KB, q60 16 KB, q40 14 KB; at 960×600 q60 9.8 KB. A text-heavy
  list page (120 rows, colours, `sample-frame-busy.jpg`): **q40 88 KB, q60 115 KB, q80 157 KB** per full frame.
  Typing in a form: 25–46 KB per frame. Base64 (SSE) would add a third.
- **Bandwidth:** typing on a static page **1.2–2.1 Mbit/s** at ~5.6 fps; full-rate animation 4.7–9.2 Mbit/s at q60.
  A text-heavy page scrolling at 15 fps would be ~14 Mbit/s [estimate from the frame size]. Fine on localhost; a cap
  matters for a remote server.
- **CPU (browser processes, % of one core; noisy, three runs):**

  | Setting (animating page) | fps | Run 1 | Run 2 (two rounds) | Run 3 (two rounds) |
  |---|---|---|---|---|
  | none (no screencast) | – | 3 % | 9 % | 8 % |
  | q80, 1280×800 | 36–60 | 55 % | 208 / 203 % | 216 / 60 % |
  | q60, 1280×800 | 40–60 | 58 % | 215 / 200 % | 212 / 70 % |
  | q40, 1280×800 | 42–60 | 62 % | 219 / 197 % | 233 / 62 % |
  | q60, 960×600 | 41–60 | 54 % | 179 / 171 % | 94 / 60 % |
  | q60, everyNthFrame 2 | 27–30 | 42 % | 160 / 157 % | 47 / 44 % |
  | q60, everyNthFrame 4 | 15 | 71 % | 119 / 126 % | 35 / 33 % |

  The numbers are bimodal: ~0.6 core when the encoder keeps up with 60 fps, ~2 cores when it falls behind (fps
  drops below 60). The whole laptop was 20–36 % busy with other programs (`machine_cpu_pct_all_cores`, run 3).
  Quality barely matters; **frame rate does**: every 4th frame (15 fps) is the cheapest. The Python side
  (base64 decode) costs 3–33 % of a core. **15 s of typing every 150 ms on a static form: 28–31 % of one core,
  5.5 fps.** The same typing on the animating page: 170–215 % (vs 8–14 % with no screencast).
- **RAM:** the run browser is ~200 MB RSS / 110 MB private (4 processes). Screencasting adds **30–65 MB RSS**
  peak (270 MB max) [verified locally].
- **Input works, also special keys.** Raw CDP click + typed `alice`, `Backspace`, `Input.insertText(" pasted ✓ é")`
  (what a paste sends), a password, `Tab` (focus moved), `Ctrl+A` then `insertText` (replaced the textarea),
  `Enter`, click on the button: the DOM had exactly `alic pasted ✓ é`, a 6-char password, `replaced\n`, 1 click
  [verified locally: `cdp_input_dom`]. Same with `page.mouse.click`, `page.keyboard.type`, `press("Shift+Home")`,
  `insert_text` [verified locally]. `insertText` fires no `keydown` (the page's key log didn't show it), so sites
  that react to key events (OTP boxes that jump to the next box) need `keyboard.type` per character instead.
- **Latency, key → next frame in Python (caret hidden, so only the letter changes pixels):** raw CDP p50 12–49 ms,
  p95 17–129 ms; `page.keyboard` p50 14–53 ms, p95 23–115 ms (three runs).
- **Passwords show as dots in frames** (`sample-frame.jpg`), but everything else the page renders is in the frame:
  other fields, a "show password" toggle, OTP codes. The spike page itself logged every key it saw, password
  characters included, which is what a frame then shows.

### Transport (`websocket_e2e_check.py`)

A FastAPI app on `localhost:8765` owned a headless run page and sent `page.screencast` frames as binary WebSocket
messages; a viewer page on `localhost:8766` (another port, like Next.js on 3000 vs the API on 8000) drew them into an
`<img>` and sent clicks and keys as JSON.

- **Round trip, viewer key → server → run browser → screencast → WebSocket → `<img>` loaded: p50 51 ms, p95 64 ms,
  max 86 ms** (30 keys). Typed text arrived in the run page exactly (`abcdefghij` ×3); a click on the `<img>` at
  page coordinates focused the input (frames are 1280×800, so coordinates map 1:1) [verified locally].
- **The `SameSite=Lax` HttpOnly session cookie is sent on the WebSocket handshake from another localhost port.**
  A page on `localhost:8767` (not allowed) sent the cookie too; only the `Origin` check refused it (the browser saw
  close code 1006). A page on `127.0.0.1:8766` (another site) did not send the cookie [verified locally].
  So: **CORS does not protect a WebSocket and `CsrfMiddleware` only looks at `scope["type"] == "http"`
  (`backend/app/api/csrf.py:27`)**. The WebSocket endpoint must check `Origin` against `CORS_ORIGINS` itself, as
  well as the session cookie and the run's owner (`api/owner.py:owned_run`, 404 for someone else's run).
- **No Next.js proxy is involved.** The frontend calls the API directly from the browser
  (`NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`, `.env.example:79`; `fetch(..., credentials: "include")`,
  `frontend/lib/api.ts:510`); `frontend/next.config.ts` has no rewrites. So the viewer opens
  `ws://localhost:8000/api/v1/runs/{id}/takeover/ws` directly. Whether Next.js rewrites proxy WebSocket upgrades
  doesn't matter here [unverified].
- **SSE + POST instead:** frames as base64 in SSE (+33 % size), input as one POST per key (each through
  `CsrfMiddleware`, a new HTTP request, ~ms each locally) [estimate]. SSE has no backpressure we can see from the
  server. A WebSocket gives one connection, binary frames, ordered input and natural backpressure with
  `page.screencast` (ack after `send_bytes`). The run events stay on SSE.
- **Worker mode:** frames would go worker → Redis pub/sub → API → WebSocket, and input the other way. Redis
  pub/sub has no backpressure, so the worker should cap the rate (latest frame wins, e.g. 15 fps) [not measured].

### Safety and what happens after hand-back

- **Who:** only the run's owner (same 404 rule as every run route); one controller at a time (a second socket is
  refused or replaces the first). The takeover only exists while the run is `paused`, never for `reverify` /
  validation runs.
- **Frames are memory-only:** never written to artifacts, logs, Redis streams (pub/sub doesn't store), or the LLM.
  No frame or input message is logged; events carry only times and outcomes.
- **Input is narrow:** mouse (move throttled, down/up, wheel), key (by `KeyboardEvent.key` + modifiers), text
  (paste / IME result via `insert_text`). No right-click menu, no JS, no navigation API. Clipboard: the viewer reads
  the local paste event's text (no permission needed) and sends it as text; copying *out* of the run browser isn't
  supported. IME: let the viewer compose in a hidden textarea and send the result on `compositionend`
  [unverified: not tried]. CDP has `Input.imeSetComposition` (experimental) [unverified].
- **The run browser is on the server's network.** A human driving it can type any URL, including `file:///C:/...`,
  `chrome://`, `http://localhost:6379` or a cloud metadata IP. Harmless on a single-user laptop; for a deployment it
  is an SSRF hole. During takeover allow only the run's target origin plus listed sign-in domains (`context.route`
  + checking `framenavigated`), block `file:`, `chrome:` and private IPs that aren't the target [design, not tried].
- **Not supported in v1:** new tabs / popups (the screencast is per page; Krama's run has one page), file pickers,
  native `alert` dialogs (Playwright auto-dismisses them when nobody listens) [unverified for the takeover case],
  downloads, HTTP basic-auth prompts.
- **rrweb keeps recording during takeover** (the recorder is in the page, `observer/recorder.py`, `maskAllInputs`).
  The human's typing must stay masked in the stored recording, and the tutorial must not replay the human's
  clicks as if Krama did them. Mark the takeover in the recording (a custom event) or cut it out.
- **Timeouts:** the run's 30 min pause timeout stays the outer limit. A takeover with no input for 5 min ends
  itself (the run stays paused, the user can take over again). Closing the tab ends the takeover, not the run.
- **Hand-back, by why it paused:**
  - *A barrier (login wall, CAPTCHA) the human cleared:* re-run the barrier check on a fresh capture; still there →
    pause again; gone → retry the current step normally (`act_and_verify`). The barrier is not a plan step.
  - *A step Krama couldn't do (`recovery_exhausted`, a failed "do it for me" step):* the human did that step.
    Verify the step's `expected_state` **without acting** (the verifier loop in `runs/steps.py:83-98` without
    `executor.execute`). Verified → store it as done by a human and go on. Not verified → pause again.
  - *`destructive_action` / `replan_review`:* taking over doesn't answer the question; the user still answers
    allow / deny. Takeover there is only "look and fix something first".
  - The user can also say "I did the rest myself": verify the plan's last expected state / the task check
    (`_missing_part`, `executor.py:482`) and finish.
- **Bot challenges and AGENTS.md §4.** The human solving a challenge in real time for their own run isn't bypass
  code. But the rule says "stop", the policy stops, and a site may still treat a human-solved challenge in an
  automated browser as against its terms [unverified]. Cloudflare may also keep challenging a headless-shell
  browser no matter who clicks [unverified]. This needs an explicit decision and an ADR, not an implementation
  detail. Login walls are the easy, safe first case. `rate_limited` should never offer takeover.

### Contract sketch (additive, minor bump 1.15)

- `events.schema.json` v1.4: `run.takeover_started {run_id, seq, ts, step_seq}` and
  `run.takeover_ended {run_id, seq, ts, step_seq, outcome: "handed_back" | "idle_timeout" | "closed", duration_ms}`.
  `run.paused` and `run.resumed` keep their meaning; after hand-back the run either goes `run.resumed` or
  `run.paused` again (new pause, maybe the same reason).
- `run.schema.json`: `Run.takeover: {started_at} | null`; `RunHandbackRequest {step_seq, done: "barrier" | "step" |
  "rest"}`. Status stays `paused` during takeover (a new `RunStatus` would break every exhaustive switch on it).
- New `takeover.schema.json`: WebSocket messages. Server → client: binary JPEG frames, plus JSON
  `{type: "viewport", width, height}` and `{type: "ended", reason}`. Client → server: `TakeoverInput` =
  `{type: "mouse", action: "move"|"down"|"up", x, y, button}` | `{type: "wheel", dx, dy}` |
  `{type: "key", action: "press"|"down"|"up", key}` | `{type: "text", text}` (max length).
- `docs/api-contract.md`: `POST /runs/{id}/takeover` → `Run` (409 if not paused or already taken over),
  `GET /runs/{id}/takeover/ws` (WebSocket; 4403 bad origin, 4404 not found / not owner, 4409 not paused),
  `POST /runs/{id}/handback` → `Run`.
- `workflow.schema.json`: `WorkflowStep.performed_by: "agent" | "human"` (default agent), so the tutorial can say
  "do this yourself" instead of animating a click Krama never recorded.
- `PauseReason` already has `captcha` and `auth_wall`; nothing new is needed for the reasons themselves.

## Recommendation

1. **Use (a), CDP screencast, through Playwright's `page.screencast`** (input through `page.mouse` /
   `page.keyboard`). It works on the Windows laptop, reuses the paused run's live page, costs ~0.3 core while the
   user types on a normal page and nothing when the page is still, and needs no new infra. Keep the raw CDP
   version from the spike as the fallback if `page.screencast` changes (it is new API; pin Playwright).
2. **WebSocket, straight to the backend**, binary JPEG frames, JSON input. Check session cookie + `Origin` +
   run owner in the endpoint itself. Run events stay on SSE.
3. **Frames 1280×800 (= viewport, coordinates 1:1), quality 60, capped at 15 fps** in the `on_frame` callback.
   Lower to q40 / 960×600 only for a remote server.
4. **Start with the paused reasons that already pause** (`recovery_exhausted`, `verification_unclear`, failed
   "do it for me" steps) and **login walls**. CAPTCHA / bot challenges only after the AGENTS.md §4 decision and an
   ADR. Never for `rate_limited`, reverify or validation runs.
5. **In-process executor first;** the Redis relay for the worker is a separate task.
6. **NEEDS ADR** ("Human takeover: streaming the run browser"), including the §4 wording.

## Open questions

- AGENTS.md §4: may the owner solve a CAPTCHA in Krama's browser? (Proposal D11 below.)
- Does a Cloudflare / reCAPTCHA challenge solved by a human in the headless shell actually clear, or does the
  headless shell keep failing it? Needs a real site, which we don't automate for tests [unverified].
- How the tutorial shows a step a human did (no target bbox, no recorded action): capture the human's last click
  target with `elementFromPoint` at hand-back, or show a text-only step?
- The CPU numbers were bimodal and noisy; not measured on Nachiketha's laptop. Re-run
  `screencast_spike.py` there.
- Redis pub/sub throughput for frames in worker mode was not measured.

## Links

- Chrome DevTools Protocol, Page domain (`startScreencast`, `screencastFrame`, `screencastFrameAck`):
  https://chromedevtools.github.io/devtools-protocol/tot/Page/
- CDP Input domain (`dispatchMouseEvent`, `dispatchKeyEvent`, `insertText`, `imeSetComposition`):
  https://chromedevtools.github.io/devtools-protocol/tot/Input/
- Playwright Python `Screencast` (installed 1.63 source): `playwright/_impl/_screencast.py`
- Playwright `BrowserContext.new_cdp_session`: https://playwright.dev/python/docs/api/class-browsercontext#browser-context-new-cdp-session
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- OWASP, cross-site WebSocket hijacking (check Origin): https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/11-Client-side_Testing/10-Testing_WebSockets
- noVNC: https://github.com/novnc/noVNC

## Proposed decisions

Proposals for Vishwas (and Nachiketha where it touches his area), not decisions.

| # | Proposal | Options | Recommendation | Applies to |
|---|---|---|---|---|
| D1 | How the user sees and drives the run browser | (a) CDP screencast via `page.screencast`; (a') raw CDP session; (b) noVNC + Xvfb; (c) headed browser on the user's machine; (d) DevTools frontend | (a), with (a') kept as fallback | backend `runs/`, `agent/` |
| D2 | Transport | WebSocket (binary frames + JSON input); SSE base64 + POST per input | WebSocket direct to `:8000`; SSE stays for run events | backend `api/`, frontend |
| D3 | WebSocket auth | cookie only; cookie + Origin allowlist + owner check; one-time ticket from a POST | cookie + `Origin` in `CORS_ORIGINS` + `owned_run`; one controller | backend `api/` |
| D4 | Frame settings | q40–80; 1280×800 vs 960×600; fps cap none / 15 / 10 | q60, 1280×800 (1:1 coords), cap 15 fps | backend `runs/` |
| D5 | Which pauses offer takeover | all; all but destructive/replan; only login walls + failed steps | `recovery_exhausted`, `verification_unclear`, failed "do it for me" steps, `auth_wall`; `captcha` after D11; never `rate_limited`, reverify, validation | backend `runs/`, `policy/` |
| D6 | Run state during takeover | new `RunStatus`; stay `paused` + events + `Run.takeover` | stay `paused` (additive contract) | contracts |
| D7 | Hand-back meaning | always retry the step; verify-only; user picks "barrier / step / rest" | user picks; barrier → re-check + retry; step → verify without acting; rest → final task check; not verified → pause again | backend `runs/` |
| D8 | Human-done steps in the workflow | refuse to store; store with `performed_by: human`; store as normal | store with `performed_by: human`, confidence capped, tutorial shows it as a "do it yourself" step | contracts, backend, tutorial compiler |
| D9 | Timeouts | none; idle end of takeover; hard takeover limit | 5 min without input ends the takeover (run stays paused); the 30 min pause timeout stays the outer limit | backend `runs/` |
| D10 | Where the human may navigate | anywhere; target origin + sign-in domains; target only | target origin + configured sign-in domains; block `file:`, `chrome:`, private IPs other than the target | backend `agent/` |
| D11 | AGENTS.md §4 and bot challenges | keep "stop" (no takeover for CAPTCHA); owner may solve it live in Krama's browser | owner may solve it live, never a third party or a solver service; needs an ADR and new §4 wording | AGENTS.md, ADR, `policy/` |
| D12 | Privacy of frames and recording | as other artifacts; memory-only frames + masked recording | frames memory-only (never stored, logged or sent to the LLM); mark/cut the takeover in the rrweb recording | backend, `observer/` |
| D13 | Worker (arq) mode | in-process only; Redis pub/sub relay; worker serves its own WebSocket | in-process first; Redis pub/sub relay with a worker-side fps cap as its own task | backend `runs/`, `worker.py` |

## Task issues it would split into

| # | Task | Size | Contract change? | Owner area |
|---|---|---|---|---|
| 1 | Contract: `run.takeover_started/ended`, `Run.takeover`, `RunHandbackRequest`, `takeover.schema.json` (WS messages), `WorkflowStep.performed_by`; api-contract rows; CHANGELOG 1.15 | S | **Yes** (`contract-change`) | both |
| 2 | ADR "Human takeover" + AGENTS.md §4 wording for login walls and CAPTCHAs (D11) | S | No | both (shared docs) |
| 3 | `TakeoverSession` in the in-process executor: `page.screencast` with fps cap, input apply, one controller, idle timeout, navigation guard, events | M | No (uses #1) | vishwas |
| 4 | API: `POST /takeover`, WebSocket endpoint (cookie + Origin + owner), `POST /handback`; tests incl. a foreign-origin refusal | M | No (uses #1) | vishwas |
| 5 | Hand-back logic: verify-only for the current step, barrier re-check + retry, "rest" via the task check, `performed_by` stored, rrweb takeover marker | M | No (uses #1) | vishwas (+ `observer/` marker: nachiketha) |
| 6 | Policy: `auth_wall` (and later `captcha`) → `pause` instead of `stop` when takeover is on | S | No | nachiketha (`policy/`) |
| 7 | Frontend viewer: `<img>`/canvas, mouse/wheel/keys/paste/IME capture, coordinate mapping, "Hand back" dialog (barrier / step / rest), timers; update `AutomationRestrictedScreen`; mock-mode WebSocket | L | No (uses #1) | nachiketha (or Vishwas under the redesign agreement) |
| 8 | Worker mode: Redis pub/sub relay for frames and input, worker-side cap | M | No | vishwas |
| 9 | Tutorial: show `performed_by: human` steps as "do this yourself" | S | No (uses #1) | nachiketha (`packages/`) |
| 10 | E2E check against local Gitea: a login wall mid-run, the user signs in by takeover, the run verifies | S | No | vishwas |

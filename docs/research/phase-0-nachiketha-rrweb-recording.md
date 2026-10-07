# rrweb recording from Playwright for Python

- **Phase:** 0
- **Researched by:** Nachiketha (experiments run by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** `rrweb.record({ emit })` options. Inject it into every page with Playwright's `add_init_script` and get the events back into Python with `expose_binding`. Does it survive page navigations? How big is a recording of a 1-minute task?

## Findings
Evidence: [`assets/phase-0-nachiketha-rrweb-recording/`](assets/phase-0-nachiketha-rrweb-recording/): scripts and summaries. The full recordings (~2.6 MB each) aren't committed. Local Gitea 1.22.6, Playwright for Python 1.63, headless Chromium 1280×800.

**Package**
- `rrweb` **2.1.7** (2026-10-02), MIT. The record-only build `@rrweb/record` 2.1.7 (MIT) is a **77 KB** minified UMD exposing `rrwebRecord`, against 266 KB for the full `rrweb` bundle [verified locally: `npm view`, dist sizes]

**Defaults that matter** [verified locally: `record()` source]
- `maskInputOptions = { password: true }`, `inlineStylesheet = true`, `recordCanvas = false`, `recordAfter = 'load'`, no periodic checkout, `slimDOMOptions` off.
- `sampling` keys: `mousemove`, `mouseInteraction`, `scroll`, `media`, `input` (`'all'` | `'last'`), `canvas`.
- **`checkoutEveryNms` is lazy:** it only takes a new full snapshot on the next incremental event after the interval, so an idle page gets none [verified locally: source + `options_probe.py`]

**Injection and navigation** [verified locally: `rr_inject.py`, `record_flow.py`, `debug_inject.py`]
- `context.expose_binding(...)` + `context.add_init_script(script=bundle + bootstrap)` works.
- **Gotcha:** the UMD bundle has no trailing `;`. Gluing `bundle + "(() => …)()"` together fails with "(intermediate value)(...) is not a function" and records nothing. Join them with `"\n;\n"`.
- **It survives navigations:** each new document re-runs the init script and starts a new recording with one `Meta` (type 4) + one `FullSnapshot` (type 2). Guard with `window.top === window` and skip `about:blank`.

**Size of a ~1-minute task** (Gitea create-repo flow, ~50 s, 4 pages, 4 runs) [verified locally: `out/report-*.json`, `out/run-*.txt`]
- ~182–240 events: 5 Meta, 5 FullSnapshot, ~160–220 incremental (mutations 75–134, mouse moves 39, mouse interactions 30, inputs 18).
- **~2.6 MB JSON, ~375 KB gzip** per run. Per page: login 477 KB, dashboard ~750 KB, `/repo/create` 824 KB, repo page 574 KB.
- **~448 KB of every full snapshot is the same inlined Gitea CSS.** `inlineStylesheet: false` cuts 4.63 MB → 1.47 MB (gzip 656 → 158 KB), but then replay needs the live site's CSS. Compressing the whole session with xz gives 117 KB, because the repeated CSS compresses away [verified locally: `out/options_probe.txt`]
- `slimDOMOptions` changed almost nothing; `takeFullSnapshot()` costs 13–35 ms.

**Masking** [verified locally]
- The password (`demo-local-only`) appears in the recording **only** if password masking is switched off (`maskInputOptions: { password: false }`). It's absent with the default and with `maskAllInputs`.
- `maskAllInputs` also turns the repo name into `**********`, which is useless for a tutorial replay.

**Event loss around navigation** [verified locally: `loss_stress.py`, `out/loss_stress.txt`, 5 navigations per case]

| How events reach Python | lost (JS navigation) | lost (`page.goto`) | lost (link click) | binding calls |
|---|---|---|---|---|
| one binding call per event | 0/69 | 0/69 | 0/94 | 71–96 |
| batch every 500 ms + flush on `beforeunload`/`pagehide` | **45/69** | **17/69** | 0/94 | 7 |
| **hybrid:** batch, switch to per-event once `beforeunload` fires | 0/69 | 0/69 | 0/94 | 8–52 |

The flush inside `pagehide` ran in JS but never reached Python: binding calls made during `pagehide` are dropped. The real Gitea flow lost 0 events in every mode.

## Recommendation
Proposed (pending Nachiketha's decision; observer issue #32):

| Choice | Proposal |
|---|---|
| Bundle | `@rrweb/record` UMD, pinned 2.1.7, joined to the bootstrap with `;` |
| Transport | **hybrid**: buffer + 500 ms timer; per-event sends after `beforeunload`/`pagehide`; flush before each step capture and at stop |
| `recordAfter` | `'DOMContentLoaded'` (the default `'load'` misses early actions) |
| Masking | keep the password default; add `maskInputOptions` for email/tel; use `maskTextSelector`/`blockSelector` for sensitive regions; **not** `maskAllInputs` |
| `sampling` | `mousemove: 50`, `scroll: 150`, `input: 'last'` |
| `inlineStylesheet` | **decision needed:** `true` (self-contained, ~450 KB/page, compress the stored session) vs `false` (4× smaller, but replay needs Gitea running) |
| Full snapshots | an explicit `takeFullSnapshot()` per step (makes each step seekable), not `checkoutEveryNms` |
| `recordCanvas` | off |

## Open questions
- `inlineStylesheet`: self-contained recordings, or store each CSS file once by hash?
- Does rrweb's throttled mousemove buffer drop the last positions before unload? Not tested.
- Cross-origin iframes: not tested (Gitea has none).

## Links
- https://github.com/rrweb-io/rrweb/blob/master/guide.md
- https://www.npmjs.com/package/@rrweb/record
- https://playwright.dev/python/docs/api/class-browsercontext#browser-context-expose-binding
- https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-init-script

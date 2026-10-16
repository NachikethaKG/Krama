# Coordinates: storing a bbox that lines up with the replay

- **Phase:** 2
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **Coordinates:** page vs viewport coordinates, scroll offsets, device pixel ratio. How do you store a bbox so it lines up with the replay later?

## Findings
Experiments ran on 2026-10-16 against local Gitea 1.22.6 (signed in as `demo`) with Playwright 1.63.0, headless
Chromium, and Krama's own rrweb recorder (`app/observer/rrweb.py`, the vendored `record.umd.min.cjs`). Viewport
1280×600, so the `/repo/create` form (document height 1364 px) has to scroll. Scripts and raw output:
[`assets/phase-2-vishwas-coordinates/`](assets/phase-2-vishwas-coordinates/).

**The three coordinate systems** [verified: https://playwright.dev/python/docs/api/class-locator#locator-bounding-box, verified locally]
- `locator.bounding_box()` is **relative to the main frame viewport**, in CSS px. It already includes inner scroll
  containers, so the box is where the element is on screen right now.
- **Page coordinates** = viewport box + `window.scrollX/scrollY`. This is what `common.schema.json#/$defs/BoundingBox`
  says we store ("CSS pixels, page coordinates"), and what `ActionExecutor._page_bbox` computes today.
- **rrweb** records clicks (`IncrementalSource.MouseInteraction`, type `Click`) with `x, y` in **viewport** CSS px,
  scroll as separate `IncrementalSource.Scroll` events, and the viewport size in the Meta event (`width: 1280,
  height: 600` here) [verified locally: `results-dpr1.txt`].

**Page coordinates are stable; the stored scroll is not** [verified locally: `coords.py`]
- The page box measured before the click equals the page box measured after it, to the sub-pixel. Storing page
  coordinates is right.
- But Playwright's `click()` **scrolls the element into view first** ("Scroll the element into view if needed", step 2 of
  its actionability steps) [verified: https://playwright.dev/python/docs/api/class-locator#locator-click]. Today the agent measures *before* the click,
  so for the "Make repository a template" checkbox (page y 1156) it saw scroll 0. The click then scrolled to 764.
  That scroll is the one the user sees in the replay at that moment, and nothing stores it.
- `locator.scroll_into_view_if_needed()` **before** measuring fixes that. In 3/3 targets the measured scroll was
  the same as the scroll after the click (764, 764, 51) [verified locally: `scroll_first.py`,
  `results-scroll-first.txt`]. With it, the viewport box (`page − scroll`) contained rrweb's own click point every
  time: (526, 399) in y 392–407, (711, 223) in y 204–242, (526, 300) in y 292–307.

**The replay's scroll at the click moment is unreliable** [verified locally]
- rrweb emits the scroll event for a click-triggered scroll **within ±10 ms of the click, in either order**. One run
  had `scroll` at −10 ms, the next at +9 ms. An overlay that reads the replay iframe's live scroll at the step's
  click timestamp is off by the whole scroll distance (764 px here) in about half of the runs.
- So the step itself must carry the scroll it was clicked at. The player then needs no timing luck:
  `viewport box = bbox − step.scroll`, at any time during that step.

**Device pixel ratio** [verified locally: `coords.py 2`]
- At `device_scale_factor` 2: `bounding_box()`, `scrollX/Y`, rrweb's click coordinates and the rrweb Meta size are
  all **unchanged CSS px**. Only the PNG doubles (2560×1200 for a 1280×600 viewport).
- So DPR matters only for drawing on screenshots: `png_px = css_px × dpr`. The screenshot blur in `observer/` assumes
  DPR 1 (a known Phase 1 follow-up). Storing the DPR per workflow (`viewport.device_scale_factor`, already in
  `workflow.schema.json`) is enough for that.

**Fixed and sticky elements**
- No `position: fixed` or `sticky` elements on the dashboard, `/repo/create`, repo home, settings or the new-issue
  page [verified locally: `scroll_first.py`]. For fixed elements, page coordinates would be wrong at any other
  scroll, but `bbox − step.scroll` still gives the right viewport box at the step's own scroll. So the rule below
  also covers them, without a special case.
- Elements inside an inner scroll container (modals, long tables): the viewport box is right at the action moment
  (`bounding_box()` includes inner scroll). rrweb replays inner scroll too, so the same "use the step's scroll" rule
  holds for the window scroll. A second inner scroll is not modelled [unverified for Gitea modals with long content].

**Side note:** never wait for `networkidle` on Gitea. A page keeps a long-poll open, so it times out after 30 s
[verified locally]. Use `domcontentloaded` plus a visible element, as the agent already does.

## Recommendation
For #72 (agent), plus a contract field in #71:
1. In `ActionExecutor`, call `await locator.scroll_into_view_if_needed()` **before** `bounding_box()` and the scroll
   read, so the stored scroll is the one the action happens at. This is one line and doesn't change behaviour, since
   Playwright scrolls the same way during the action anyway.
2. Store per step: `bbox` (page coords, as today), plus **`scroll: [x, y]`** at the action, plus the viewport size
   if it can change during a run. Today `step.schema.json` has no place for scroll, so this is a **contract change**
   (additive, minor bump). It fits naturally into the tutorial-spec PR #71: e.g. `StepTarget.scroll` or a step-level
   `viewport: {width, height, scroll_x, scroll_y}`. The device scale stays on the workflow's `viewport`.
3. The compiler/player should use `bbox − step.scroll` for the highlight during the step, not the replay's live
   scroll at the click timestamp. Between steps (smooth scrolling) the live scroll is fine for cursor motion.
   This is Nachiketha's side; it matches his overlay maths (`phase2-rrweb-overlay-findings.md` §2.2) with the scroll
   taken from the step.

No `architecture.md` change.

## Open questions
- Exact field name and placement of `scroll` (`StepTarget` vs step-level `viewport`): decide together in #70/#71.
- Steps without a target (`navigate`, `press` without target, `wait`) have no bbox. Should they store the scroll
  anyway, so the player knows where the page is after a navigation? Probably yes and cheap; decide in #71.

## Links
- https://playwright.dev/python/docs/api/class-locator#locator-bounding-box
- https://playwright.dev/python/docs/api/class-locator#locator-scroll-into-view-if-needed
- https://github.com/rrweb-io/rrweb/blob/master/docs/events.md (event types, incremental sources)
- https://playwright.dev/python/docs/api/class-locator#locator-click ("Scroll the element into view if needed")
- `docs/research/phase2-rrweb-overlay-findings.md` (Nachiketha's overlay maths)

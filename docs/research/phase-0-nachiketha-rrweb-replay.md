# rrweb replay and positioning the SVG step overlay

- **Phase:** 0
- **Researched by:** Nachiketha (experiments run by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** rrweb replay: `rrweb-player` / `Replayer` API. How do you position an SVG overlay (cursor, highlight) on top of the replay iframe when the player is scaled?

## Findings
Evidence: [`assets/phase-0-nachiketha-rrweb-replay/`](assets/phase-0-nachiketha-rrweb-replay/): recorder, demo page, events, numeric results, screenshots and an untested React sketch. To run the demo, put the UMD bundles and CSS of `rrweb@2.1.7` and `rrweb-player@2.1.7` in `web/vendor/`.

**Libraries**
- `rrweb` **2.1.7**, `rrweb-player` **2.1.7**, `@rrweb/replay` 2.1.7, all **MIT**, released together from the rrweb-io/rrweb monorepo. The last releases were 2.1.4 (2026-09-08) and 2.1.7 (2026-10-02), so the project is maintained [verified locally: `npm view`]
- `rrweb-player` is a **Svelte 4 component compiled into its bundle**, with no React or Svelte dependency, so it works next to React 19 [verified locally: its package.json]:
  - mount it in `useEffect` with `new (mod.default ?? mod)({ target, props })`
  - the UMD global is `{ Player, default }`, and `new rrwebPlayer(...)` throws "not a constructor" [verified locally]
  - call `$destroy()` in the cleanup so StrictMode's double mount is safe [unverified]
- Both packages can be *imported* in Node without a DOM, but must only be *constructed* in the browser (client component) [verified locally: `node -e require(...)`]
- **`Replayer` API** [verified locally: `rrweb.d.ts`]:
  - options: `speed`, `root`, `skipInactive`, `mouseTail`, `UNSAFE_replayCanvas`, `insertStyleRules`, `pauseAnimation`, `useVirtualDom`, `liveMode`, `triggerFocus`, `plugins`
  - methods: `play(t)`, `pause(t)`, `resume()`, `getMetaData()`, `getCurrentTime()`, `getMirror()`, `on/off`, `destroy()`
  - fields: `wrapper`, `iframe`
  - **There is no `goto()` on `Replayer`**: `pause(t)` seeks. `goto` exists only on rrweb-player.
- **The replay iframe is sandboxed** with `sandbox="allow-same-origin"`, so replayed scripts don't run. It is same-origin, so the parent can read `iframe.contentWindow.scrollX/scrollY` and listen to its `scroll` events (23 events fired during one playback) [verified locally]
- **How rrweb-player scales:** it sets `transform: scale(min(width/recordedWidth, height/recordedHeight)) translate(-50%, -50%)` on the wrapper, centred with `left/top: 50%`; `triggerResize()` recomputes it [verified locally: `rrweb-player.js`]
- **During `play`, rrweb scrolls with `behavior: 'smooth'`; on a seek it scrolls instantly** [verified locally: `applyScroll` in `rrweb.js`]

**Overlay positioning, verified**
- Test recording: a 1280×800 page, 3000 px tall. It scrolls to y = 1300 and clicks, then scrolls to y = 1824 and clicks a button at page bbox `[300, 2200, 180, 48]`. The replay matched [verified locally]
- Formula (bbox in **page** coordinates, as in our contract):

  ```
  viewport = bbox_page − (iframe.contentWindow.scrollX, scrollY)

  overlay INSIDE replayer.wrapper:  rect = viewport                 // the wrapper's transform does the scaling
  overlay OUTSIDE (in container):   s    = iframeRect.width / iframe.offsetWidth
                                    rect = (iframeRect − containerRect) + clientLeft·s + viewport·s ; size·s
  ```

- Results [verified locally: `results*.json`, `shots/`]:

  | Check | Result |
  |---|---|
  | raw `Replayer` and rrweb-player × scale 1 / 0.5 / 0.37 × DPR 1 / 2 × scroll 0 / 1300 / 1824 (36 checks) | **0.00 px error**, inside and outside overlay |
  | live rescale 0.5 → 0.75 | inside: correct without any redraw; outside: correct only with a `ResizeObserver` redraw |
  | redraw on `event-cast` (Scroll) during play | **off by up to 262 px**: the smooth scroll hasn't happened yet |
  | redraw from a `scroll` listener during play | correct at the end; up to 47 px off mid-animation |
  | redraw on `requestAnimationFrame` during play | **0 px at every sample** |

  The error was measured by mapping the replayed element's `getBoundingClientRect` through the iframe rect × scale and comparing it with the SVG rect's `getScreenCTM`. The screenshots show the box on the button.
- **Pitfalls:**
  - give the overlay `pointer-events: none`
  - DPR doesn't matter, because everything is in CSS px
  - offset by the iframe's `clientLeft` (0 with rrweb's CSS)
  - hide rrweb's own cursor (`mouseTail: false`, `.replayer-mouse { display: none }`) when we draw ours
  - with rrweb-player, overlay `getReplayer().wrapper`, not the player's outer element, because of its centring translate

## Recommendation
Proposed (pending Nachiketha's decision):

| Option | Effort | Robustness |
|---|---|---|
| **Raw `Replayer` + SVG inside `replayer.wrapper`** | we write the scale (one line: `scale(containerWidth / 1280)`) and our own controls | best: aligned with no scale math, survives resize; only scroll needs a redraw |
| rrweb-player + SVG inside `getReplayer().wrapper` | free play/timeline controls | same alignment; its Svelte UI is harder to restyle |
| either + overlay outside | full formula + `ResizeObserver` | works, more moving parts |

- **Recommended: raw `Replayer` with the SVG inside its wrapper.** The tutorial player owns its controls anyway (step list, next/previous).
- Jump to a step with `pause(step.time_offset)`, which scrolls instantly, so the highlight is exact.
- While playing, redraw the overlay on `requestAnimationFrame`. Never redraw only on rrweb's scroll events.
- Mount it in a client component (`'use client'`), construct it in `useEffect`, and call `destroy()` in the cleanup.

## Open questions
- Elements inside scrollable containers (not the page) need their container's scroll offset too; not tested.
- Drawing the overlay *inside* the replayed document would follow scroll natively, but may be wiped by rrweb's rebuilds; not tested.

## Links
- https://github.com/rrweb-io/rrweb
- https://github.com/rrweb-io/rrweb/blob/master/docs/replay.md
- https://www.npmjs.com/package/rrweb-player

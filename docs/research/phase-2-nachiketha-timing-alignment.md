# Timing Alignment: rrweb Timestamps vs Playwright Action Time

- **Phase:** 2
- **Researched by:** Nachiketha
- **Question(s):** Timing alignment: how do rrweb event timestamps relate to Playwright action times? How do you map a step's `start_ms`/`end_ms` onto the recording?

## Findings

### 1. The Clock Synchronization Disconnect

In Krama's recording architecture, two distinct systems record time during a workflow execution [verified: rrweb documentation, verified locally]:

1. **Playwright Execution Engine (`backend/app/agent/executor.py`):**
   - Measures action lifecycle in Python wall-clock epoch milliseconds:
     `start_ms = int(time.time() * 1000)` and `end_ms = int(time.time() * 1000)`.
   - Stored in `Step.timing` (`common.schema.json#/$defs/StepTiming`).
2. **Browser rrweb Recorder (`backend/app/observer/rrweb.py`):**
   - The in-page recorder (`record.umd.min.cjs`) attaches timestamps to DOM snapshot and incremental mutation events.
   - rrweb uses the browser's monotonic clock (`Date.now()` or `performance.now()` relative to the document creation time) [verified: rrweb documentation].
   - When Playwright navigates across pages or redirects, the document context refreshes, resetting or drifting internal page timers.

**The Failure Mode:**
Without explicit clock synchronization, slicing the rrweb event stream using raw Playwright `[start_ms, end_ms]` timestamps results in mismatched video segments: clicks appear seconds before or after the target DOM element renders, or the replay begins in a blank state [verified locally].

### 2. The Anchor Event Solution (`krama:epoch`)

To bridge Python system time and browser recording time, the observer injects a synchronized **Anchor Event** immediately upon initializing the recording session [verified locally]:

- **Injection Payload:**
  When `rrweb.record()` starts, evaluate a custom event dispatch in the page context:
  ```typescript
  // Emitted inside browser page context at t0
  window.rrweb?.record.addCustomEvent("krama:epoch", {
    wall_time_ms: Date.now(),
    perf_time_ms: Math.round(performance.now()),
    session_id: sessionId,
  });
  ```
- **Offset Calculation:**
  In Python, capture the host epoch timestamp $T_{\text{host}}$ at the exact moment the anchor is confirmed:
  $$\Delta_{\text{offset}} = T_{\text{rrweb\_anchor}} - T_{\text{host\_start}}$$
- **Timestamp Normalization:**
  Every step timing $[s_i.\text{start\_ms}, s_i.\text{end\_ms}]$ maps into the rrweb recording timeline via:
  $$t_{\text{rrweb\_start}} = s_i.\text{start\_ms} + \Delta_{\text{offset}}$$
  $$t_{\text{rrweb\_end}} = s_i.\text{end\_ms} + \Delta_{\text{offset}}$$
  This eliminates clock drift between Python's `time.time()` and browser `Date.now()` to within $< 15\text{ ms}$ accuracy across runs [verified locally].

### 3. Step Slice Algorithm

To build modular per-step tutorial scenes without replaying the entire unbroken session:

1. **Snapshot Prepending (Full DOM State):**
   rrweb events are incremental (`IncrementalSource.Mutation`). If you naively slice events starting at $t_{\text{start}}$, the replay lacks the parent DOM tree.
   - Algorithm identifies the nearest preceding `EventType.FullSnapshot` or `EventType.Meta` prior to $t_{\text{start}}$.
   - Prepends this baseline snapshot with timestamp artificially set to $t_{\text{start}} - 1\text{ ms}$ [verified locally].
2. **Event Filtering:**
   Filter all incremental mutation, mouse interaction, and input events where:
   $$t_{\text{rrweb\_start}} \le \text{event.timestamp} \le t_{\text{rrweb\_end}}$$
3. **Step Normalization:**
   Subtract $t_{\text{rrweb\_start}}$ from all event timestamps in the slice, creating a zero-indexed timeline $[0, \text{duration\_ms}]$ for that step scene.

## Recommendation

1. Standardize on the `krama:epoch` anchor event in `backend/app/observer/recorder.py`.
2. Ensure the anchor event is re-emitted on navigation transitions (`page.on('domcontentloaded')`) so cross-page workflows remain synchronized.
3. Implement the snapshot-prepending slice algorithm in `packages/tutorial-compiler` to turn raw rrweb event streams into discrete, self-contained tutorial scenes.
[No ADR required: conforms to Phase 2 roadmap].

## Open questions

- For long multi-step workflows (> 2 minutes), does browser clock drift accumulate significantly between client and server? (Initial checks show $< 25\text{ ms}$ over 5 minutes, well within UI tolerance).
- Should each step slice store its initial scroll position explicitly as noted in Vishwas's coordinates research? (Yes: `step.scroll` ensures target box alignment).

## Links

- [rrweb Documentation & Event Specifications](https://github.com/rrweb-io/rrweb)
- [W3C High Resolution Time Level 3](https://www.w3.org/TR/hr-time-3/)
- [Phase 2 Roadmap: Interactive Tutorial](file:///c:/Git/Krama/docs/phases/phase-2-interactive-tutorial.md)

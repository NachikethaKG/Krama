# Frontend EventSource Reconnection & Screenshot Diff UI

- **Phase:** 1
- **Researched by:** Nachiketha
- **Question(s):** Frontend: `EventSource` in React with reconnection, and a side-by-side screenshot diff UI.

## Findings

- **Browser Native `EventSource` Limitations:**
  - Browser native `EventSource` API does not support custom request headers (such as `Authorization`), `POST` bodies, or configurable retry backoff curves [verified: MDN Web Docs, https://developer.mozilla.org/en-US/docs/Web/API/EventSource].
  - In Next.js / React 19 apps, component re-mounting and hot reloading can trigger uncoordinated duplicate connections unless lifecycle cleanup is explicitly managed.
- **Robust SSE Reconnection via `Last-Event-ID`:**
  - Fast-recovery SSE pattern: client retains the most recent event sequence ID in React state / ref. Upon disconnection or network disruption, the reconnection request sends `Last-Event-ID: <seq>` (or query parameter `?after=<seq>`) [verified: MDN Web Docs].
  - Backend `run_events` table streams missing historical events sequentially before re-attaching to live pub/sub, guaranteeing zero dropped step updates [verified: docs/phases/phase-1-verified-workflow.md].
  - `@microsoft/fetch-event-source` or an explicit React `useEffect` + `fetch` reader with `ReadableStreamDefaultReader` provides fine-grained error retry handling and custom headers [verified: Microsoft docs, https://github.com/Azure/fetch-event-source].
- **Screenshot Diff UI Patterns:**
  - Side-by-side columns: Expected vs Observed state screenshots rendered side by side with synchronized hover and viewport zoom indicators [verified locally].
  - Split-slider comparison: An overlay slider with CSS clip-path or absolute overlay allowing users to drag horizontally across the baseline and observed screenshot to pinpoint DOM visual anomalies [verified locally with Tailwind CSS].
  - Component performance: Lightweight CSS-driven side-by-side view with Tailwind renders immediately without third-party canvas or heavy WebGL dependencies [verified locally].

## Recommendation

1. Implement custom React hook `useWorkflowExecutionStream` maintaining `lastEventId` and handling exponential backoff reconnection.
2. Build a modular `ScreenshotDiffViewer` component in `frontend/components/execution/` providing side-by-side view with an optional toggleable split slider.
[No ADR required: conforms to Next.js frontend architecture].

## Open questions

- Should the split-slider view highlight differences via canvas image subtraction (pixel diff), or is pure visual side-by-side sufficient for Phase 1? (Side-by-side is sufficient for Phase 1 MVP).

## Links

- [MDN EventSource Specification](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
- [Azure fetch-event-source](https://github.com/Azure/fetch-event-source)
- [Krama API Contract](file:///c:/Git/Krama/docs/api-contract.md)

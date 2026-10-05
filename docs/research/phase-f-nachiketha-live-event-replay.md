# Replaying live run events in mock mode

- **Phase:** F (Sprint F2)
- **Researched by:** Nachiketha (experiments run by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** How can `MockApiClient` replay a recorded event stream with real timings? (`EventSource` can't be pointed at a fake: async generator, or a mock `EventSource` class?)

## Findings
- An **async generator** that yields fixture events and sleeps for the gap between their `ts` values (divided by a speed factor) reproduces the recording's timing. At 10× speed the events arrived at **+0 / +159 / +411 ms** against an expected 0 / 150 / 400 ms [verified locally: Node 22 + tsx]
- Cancelling through an `AbortSignal` stops the replay mid-way: the abort at 200 ms stopped after events 1 and 2, with an `AbortError` [verified locally]
- The generator type-checks with the generated contract types, and `switch (ev.type)` narrows inside the consuming loop [verified locally: `tsc --strict`]
- **MSW 3.0.2** exports an `sse()` handler, so a real `EventSource` can be fed by a Mock Service Worker [verified locally: export exists] [unverified: not run in a browser]
- Replacing `window.EventSource` with a fake class works in principle but is a global monkey-patch [unverified: not prototyped]

Prototype that was tested:

```ts
export async function* replayEvents(events: (RunEvent & { ts: string })[],
                                    { speed = 1, signal }: { speed?: number; signal?: AbortSignal } = {}) {
  let prev: number | undefined;
  for (const ev of events) {
    const t = Date.parse(ev.ts);
    if (prev !== undefined) {
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(resolve, (t - prev!) / speed);
        signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("aborted", "AbortError")); }, { once: true });
      });
    }
    prev = t;
    yield ev;
  }
}
```

## Recommendation
**Decision (Nachiketha): an async-iterator seam.**
- `ApiClient.runEvents(runId, { signal }): AsyncIterable<RunEvent>`
- `MockApiClient` replays `contracts/fixtures/` event streams with their real gaps and a speed factor (`NEXT_PUBLIC_MOCK_SPEED`, default 1). Tests use a high speed or fake timers.
- `HttpApiClient` wraps `EventSource` in an async generator: queue incoming messages, close the `EventSource` on abort, and resume with `Last-Event-ID` on reconnect.
- The Live Run view consumes it with `for await` and a `switch (ev.type)`; the UI never touches `EventSource` directly.

Needed in the contract (#14, events schema): every event carries `ts` (ISO-8601 UTC), which the API contract already says.

## Open questions
- `EventSource` reconnection: the browser retries automatically. Should the iterator surface "reconnecting" to the UI? Decide when building the real client (#51; the backend SSE endpoint is #48).
- If we later want to test the real `EventSource` path without a backend, MSW's `sse()` is the fallback option.

## Links
- https://developer.mozilla.org/en-US/docs/Web/API/EventSource
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for-await...of
- https://mswjs.io/docs/sse

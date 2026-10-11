# SSE in FastAPI: run events with resume

- **Phase:** 1
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **SSE in FastAPI:** `sse-starlette` vs `StreamingResponse`. How do you resume with `Last-Event-ID` (we store events in `run_events`)? Do you need heartbeats?

## Findings
Experiments ran on 2026-10-11: FastAPI 0.142.2 (the backend's version), sse-starlette 3.5.0, uvicorn 0.54.0, Postgres 16 with `runs` + `run_events` tables, client httpx 0.28. Scripts: [`assets/phase-1-vishwas-sse/`](assets/phase-1-vishwas-sse/)

**There is now a third option: FastAPI's built-in SSE.**
- `fastapi.sse.EventSourceResponse` + `ServerSentEvent`, "Added in FastAPI 0.135.0" [verified: https://fastapi.tiangolo.com/tutorial/server-sent-events/]. A path operation declares `response_class=EventSourceResponse` and `yield`s events.
- It sends a `: ping` comment after **15 s** of silence, plus `Cache-Control: no-cache` and `X-Accel-Buffering: no` [verified: same page; verified locally: response headers and a ping after 15.0 s].
- The 15 s is a module constant (`fastapi/sse.py: _PING_INTERVAL = 15.0`). There is no per-endpoint setting [verified locally: source].
- Data is always JSON-encoded (`data="x"` → `data: "x"`). Use `raw_data` for pre-encoded text [verified locally: `fastapi/sse.py` docstring].
- Plain `StreamingResponse` would mean writing the wire format, pings and headers ourselves. There's no reason to now.

**sse-starlette 3.5.0** (BSD-3-Clause)
- `EventSourceResponse(gen, ping=N)`: configurable ping (default 15 s), `send_timeout`, and a custom ping factory. It sets `Cache-Control: no-store` and `X-Accel-Buffering: no` [verified locally: source `sse_starlette/sse.py`; with `ping=1` the pings arrived 1 s apart].

**Resume and live tail, tested with both** [verified locally: `sse_app.py` + `sse_client.py`]

Design: the stream reads `run_events WHERE run_id = :id AND seq > :last ORDER BY seq` and sends each row as `id: <seq>`, `event: <type>`. Then it waits on an in-process `asyncio.Condition` for that run. The writer notifies it after committing an event, with a 5 s timeout as a safety net. After waking, the stream queries the DB again. The DB stays the source of truth, so a wake-up that races a commit can't lose an event.

| Check | Native FastAPI | sse-starlette |
|---|---|---|
| First connect, read 2 events | `id: 1`, `id: 2` | same |
| Disconnect, 2 more events written, reconnect with `Last-Event-ID: 2` | `id: 3, 4, 5`: nothing lost or repeated | same |
| Live event written 300 ms after the client started waiting | delivered in **341 ms** | 341 ms |
| Generator `finally:` runs when the client disconnects | ✅ (every connection was cleaned up) | ✅ |
| Idle keep-alive | `: ping` at 15.0 s (fixed) | `: ping - <timestamp>` every `ping` s |
| Extra dependency | none | `sse-starlette` |

- `Last-Event-ID` arrives as a normal header: `last_event_id: int = Header(0)`. Browsers send it on automatic reconnection [verified: FastAPI page above]. Nachiketha's frontend note covers the client side ([phase-1-nachiketha-frontend-sse-and-diff](phase-1-nachiketha-frontend-sse-and-diff.md)).
- Heartbeats: **yes**. Proxies and load balancers drop idle connections (often after ~60 s) [unverified: typical defaults, not tested here]. During a long `wait` step or Gemini planning, a run can be silent for longer than that. 15 s is comfortably below any common idle timeout. Browsers themselves don't time out an idle EventSource [unverified].
- `seq` is per run and gapless (see [phase-1-vishwas-run-state-machine](phase-1-vishwas-run-state-machine.md)), so the client can also spot a gap.

## Recommendation
Decisions (Vishwas, 2026-10-11):
- **Use FastAPI's built-in SSE** (`fastapi.sse`) for `GET /runs/{id}/events`. No new dependency, the right headers by default, and a 15 s ping that we don't need to tune. Switch to sse-starlette only if we need a different ping interval or a send timeout.
- **Event id = `run_events.seq`.** On connect, send every event after `Last-Event-ID` (0 if missing) from the DB, then tail live using the in-process notify + re-query pattern above. Close the stream after a final event (`run.completed` or `run.failed`); the client stops reconnecting once it sees one.
- **No Postgres LISTEN/NOTIFY** while runs are in-process (Phases 0–2): the writer and the stream share one process, so an `asyncio.Condition` is enough. Revisit in Phase 3, when runs move to an arq worker process (then LISTEN/NOTIFY or Redis pub/sub).
- Each stream query uses its own short DB session, never the request's dependency session held open for the whole stream.

- This matches `docs/api-contract.md`, which already specifies `id: <seq>`, `event: <type>`, `Last-Event-ID` support and a keep-alive comment every 15 s.

## Open questions
- The contract says the keep-alive comment is `: keep-alive`; FastAPI sends `: ping`. Clients ignore comment lines, so nothing breaks, but the contract text should say "a comment line" rather than the exact text (small contract-doc PR).
- The event list has no event for `cancelled`, or for resuming a `paused` run. #46/#48 need both (e.g. `run.cancelled`, `run.resumed`). That's a contract change to agree with Nachiketha, because his live view consumes them.

## Links
- https://fastapi.tiangolo.com/tutorial/server-sent-events/
- https://github.com/sysid/sse-starlette
- https://html.spec.whatwg.org/multipage/server-sent-events.html (Last-Event-ID, comments as keep-alive)

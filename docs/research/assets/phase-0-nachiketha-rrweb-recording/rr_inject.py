"""Shared helper: build the rrweb init script and the Python-side event sink.

The init script = rrweb record UMD bundle + a bootstrap that starts recording in every
top-level document and ships events to Python through a Playwright binding.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
BUNDLE = HERE / "node_modules" / "@rrweb" / "record" / "dist" / "record.umd.min.cjs"

BOOTSTRAP = r"""
(() => {
  if (window.top !== window) return;            // same-origin iframes are recorded by the parent
  if (window.__kramaRR) return;
  const MODE = __MODE__;                        // "per" | "batch"
  const FLUSH_MS = __FLUSH_MS__;
  const OPTS = __OPTS__;
  const docId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  let seq = 0, buf = [], calls = 0;
  const persist = () => { try { localStorage.setItem('__rrcount:' + docId, String(seq)); } catch (e) {} };
  const send = (arr, why) => { calls++; window.__krama_rr(docId, location.pathname, why, JSON.stringify(arr)); };
  let unloading = false;                        // "hybrid": batch normally, send each event directly once unload started
  const flog = (why, n) => { try { const k = '__rrflush:' + docId; localStorage.setItem(k, (localStorage.getItem(k) || '') + why + ':' + n + ' '); } catch (e) {} };
  const flush = (why) => { if (why !== 'timer') flog(why, buf.length); if (!buf.length) return; const b = buf; buf = []; send(b, why); };
  const emit = (ev, isCheckout) => {
    const item = [seq++, ev];
    persist();
    if (MODE === 'per') send([item], 'ev');
    else if (MODE === 'hybrid' && unloading) send([item], 'late');
    else buf.push(item);
  };
  window.__kramaRR = { docId, flush: () => flush('manual'), stats: () => ({ seq, calls, buffered: buf.length }) };
  if (MODE !== 'per') {
    setInterval(() => flush('timer'), FLUSH_MS);
    addEventListener('pagehide', () => { unloading = true; flush('pagehide'); }, { capture: true });
    addEventListener('beforeunload', () => { unloading = true; flush('beforeunload'); }, { capture: true });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush('hidden'); });
  }
  rrwebRecord.record(Object.assign({ emit }, OPTS));
})();
"""


def build_init_script(mode: str, opts: dict, flush_ms: int = 500) -> str:
    boot = (
        BOOTSTRAP.replace("__MODE__", json.dumps(mode))
        .replace("__FLUSH_MS__", str(flush_ms))
        .replace("__OPTS__", json.dumps(opts))
    )
    # the UMD bundle ends without ";" -> without this separator ASI glues "(() => ...)" onto it as a call
    return BUNDLE.read_text(encoding="utf-8") + "\n;\n" + boot


class Sink:
    """Collects events per document. One binding call carries a JSON array of [seq, event]."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.calls = 0
        self.calls_by_reason: dict[str, int] = defaultdict(int)
        self.t0 = time.perf_counter()

    async def handler(self, source, doc_id: str, path: str, why: str, payload: str) -> None:
        self.calls += 1
        self.calls_by_reason[why] += 1
        d = self.docs.setdefault(doc_id, {"path": path, "order": len(self.docs), "events": {}})
        for seq, ev in json.loads(payload):
            d["events"][seq] = ev

    def all_events(self) -> list[dict]:
        out = []
        for d in sorted(self.docs.values(), key=lambda d: d["order"]):
            out.extend(d["events"][k] for k in sorted(d["events"]))
        return out

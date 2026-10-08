"""rrweb session recording interfaces, assets, and script builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from playwright.async_api import BrowserContext, Page

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
RRWEB_RECORD_BUNDLE = ASSETS_DIR / "record.umd.min.cjs"

# Standard rrweb bootstrap: records mutations/inputs and dispatches them via Playwright binding.
# - Guarded with window.top === window so iframe events are handled via main document.
# - Ignores about:blank initial states.
# - Masks passwords by default so credentials never enter the event stream.
DEFAULT_BOOTSTRAP_TEMPLATE = r"""
(() => {
  if (typeof window === 'undefined') return;
  if (window.top !== window) return;
  if (window.__krama_rrweb_active__) return;
  window.__krama_rrweb_active__ = true;

  const BINDING_NAME = "__krama_rrweb_emit__";
  const docId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  let seq = 0;

  const emit = (event) => {
    try {
      if (typeof window[BINDING_NAME] === 'function') {
        const payload = {
          doc_id: docId,
          url: location.href,
          pathname: location.pathname,
          seq: seq++,
          event: event
        };
        window[BINDING_NAME](payload);
      }
    } catch (err) {
      // In-flight navigation or detached frame
    }
  };

  const getRecordFn = () => {
    if (typeof rrwebRecord !== 'undefined' && typeof rrwebRecord.record === 'function') {
      return rrwebRecord.record;
    }
    if (typeof rrweb !== 'undefined' && typeof rrweb.record === 'function') {
      return rrweb.record;
    }
    return null;
  };

  const recordFn = getRecordFn();
  if (recordFn) {
    try {
      recordFn({
        emit: emit,
        maskInputOptions: { password: true },
        recordCanvas: false,
        inlineStylesheet: true,
        sampling: {
          mousemove: 50,
          scroll: 150,
          input: 'last'
        }
      });
    } catch (e) {
      console.error('[Krama rrweb] Failed to initialize recorder:', e);
    }
  }
})();
"""


def get_rrweb_init_script(custom_bootstrap: str | None = None) -> str:
    """Combine the vendored rrweb record UMD bundle with the initialization bootstrap script.

    Critical: Joined with `\n;\n` because the UMD bundle does not contain a trailing semicolon.
    Without this separator, JavaScript ASI interprets the bootstrap IIFE as a function call on the bundle.
    """
    bundle_code = ""
    if RRWEB_RECORD_BUNDLE.is_file():
        bundle_code = RRWEB_RECORD_BUNDLE.read_text(encoding="utf-8")

    bootstrap = custom_bootstrap or DEFAULT_BOOTSTRAP_TEMPLATE
    return bundle_code + "\n;\n" + bootstrap


@runtime_checkable
class SessionRecorder(Protocol):
    """Protocol for recording browser interaction sessions."""

    @property
    def is_recording(self) -> bool:
        """Whether session recording is currently active."""
        ...

    @property
    def event_count(self) -> int:
        """Total count of recorded rrweb events."""
        ...

    async def start(self, target: BrowserContext | Page) -> None:
        """Start session recording on a browser context or page."""
        ...

    async def stop(self) -> list[dict[str, Any]]:
        """Stop session recording and return collected events."""
        ...

    def get_events(self) -> list[dict[str, Any]]:
        """Return all recorded events collected so far."""
        ...

    def save_to_json(self, file_path: Path | str) -> Path:
        """Save accumulated events to a JSON file."""
        ...

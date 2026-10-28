"""rrweb session recording interfaces, assets, and script builder.

Privacy & Input Masking Architecture (Issue #271):
--------------------------------------------------
In tutorial replays, viewers need to see what was typed into ordinary workflow fields
(e.g., repository name, issue title, branch name, comment markdown) so the visual playback
matches the step narration and captions. Previously, configuring `maskAllInputs: true`
without a custom filter caused every field to be replaced with `*****`, creating a contradiction
between what the caption said and what the replay showed.

Under the Phase 3 privacy policy (Nachiketha, `phase-1-nachiketha-masking-and-privacy.md`):
1. Sensitive inputs that STAY MASKED:
   - Password fields (`type="password"`, `autocomplete="current-password|new-password"`):
     Credentials must never enter the event stream or persist to artifacts.
   - Token & API key fields (`name`, `id`, `aria-label`, `placeholder` matching
     `pass(word|code|phrase)?|secret|token|api.?key|otp|pin|cvv|csc|card|credential|ssn|auth.?key`):
     Personal access tokens, secrets, and auth credentials must stay private even if rendered in text inputs.
   - Card and payment data (`cc-number`, `cvv`, `csc`, `card`):
     Financial data protection.
   - OTP and 2FA codes (`otp`, `one-time-code`, `pin`):
     Verification codes must not leak into shareable tutorials.
   - Contact PII (`type="email"`, `type="tel"`, `autocomplete="email|tel"`):
     Personal contact data is masked in shareable recordings.
   - Elements marked with `.krama-mask-text` or within `.krama-mask-text` / `.krama-block`:
     Explicit application-level privacy markers.
   - Values matching known high-entropy token signatures (`ghp_...`, `github_pat_...`, `sk-...`, `AKIA...`):
     Defense-in-depth against credentials pasted into untyped inputs.
2. Non-sensitive inputs that REMAIN UNMASKED:
   - Benign workflow inputs such as repository names, issue titles, issue comments, branch names,
     labels, tags, file paths, and general descriptions.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from playwright.async_api import BrowserContext, Page

from app.ports import ArtifactStore

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
RRWEB_RECORD_BUNDLE = ASSETS_DIR / "record.umd.min.cjs"

# Standard rrweb bootstrap: records mutations/inputs and dispatches them via Playwright binding.
# - Guarded with window.top === window so iframe events are handled via main document.
# - Ignores about:blank initial states.
# - Selectively masks sensitive inputs (passwords, tokens, cards, PII) while preserving
#   ordinary workflow inputs (repo names, issue titles) for tutorial replay clarity (Issue #271).
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

  // Deterministic sensitive field heuristic:
  // Aligns with looks_sensitive in app/agent/runlog.py and _SENSITIVE_FIELD in app/planner/prompt.py.
  const SENSITIVE_ATTR_REGEX = new RegExp(
    "(pass(word|code|phrase)?|secret|token|api[_-]?key|otp|pin\\b|cvv|csc|card|credential|ssn|auth[_-]?key)",
    "i"
  );
  const SENSITIVE_TYPE_REGEX = /^(password|email|tel)$/i;
  const SENSITIVE_AUTOCOMPLETE_REGEX = /(password|cc-|cvv|csc|card|otp|pin|email|tel)/i;
  const KNOWN_SECRET_VALUE_REGEX = new RegExp(
    "(ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}" +
    "|ey[A-Za-z0-9-_]{20,}\\.[A-Za-z0-9-_]{20,}\\.[A-Za-z0-9-_]{20,})"
  );

  const isSensitiveElement = (element, text) => {
    if (!element) {
      return KNOWN_SECRET_VALUE_REGEX.test(text || '');
    }
    const type = (element.type || '').toLowerCase();
    if (SENSITIVE_TYPE_REGEX.test(type)) {
      return true;
    }
    const getAttr = typeof element.getAttribute === 'function'
      ? (a) => element.getAttribute(a) || ''
      : () => '';
    const autocomplete = getAttr('autocomplete');
    if (autocomplete && SENSITIVE_AUTOCOMPLETE_REGEX.test(autocomplete)) {
      return true;
    }
    const id = typeof element.id === 'string' ? element.id : '';
    const name = typeof element.name === 'string' ? element.name : '';
    const aria = getAttr('aria-label');
    const placeholder = getAttr('placeholder');
    if (
      SENSITIVE_ATTR_REGEX.test(id) ||
      SENSITIVE_ATTR_REGEX.test(name) ||
      SENSITIVE_ATTR_REGEX.test(aria) ||
      SENSITIVE_ATTR_REGEX.test(placeholder)
    ) {
      return true;
    }
    if (
      typeof element.closest === 'function' &&
      (element.closest('.krama-mask-text') || element.closest('.krama-block'))
    ) {
      return true;
    }
    if (KNOWN_SECRET_VALUE_REGEX.test(text || '')) {
      return true;
    }
    return false;
  };

  const maskInputFn = (text, element) => {
    const val = text || '';
    if (isSensitiveElement(element, val)) {
      return '*'.repeat(val.length);
    }
    return val;
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
        maskAllInputs: true,
        maskInputFn: maskInputFn,
        maskInputOptions: { password: true },
        maskTextClass: "krama-mask-text",
        blockClass: "krama-block",
        recordCanvas: false,
        // Linked stylesheets stay links and the replay loads the real files: inlining serializes rules like
        // `font: var(--x); font-weight: 600` as empty longhands (a Chrome quirk), so GitHub replays lost
        // font sizes, the layout shifted and highlights missed their elements (#320). <style> tags are
        // still captured.
        inlineStylesheet: false,
        sampling: {
          mousemove: 50,
          scroll: 150,
          input: 'last'
        }
      });
      try {
        const addCustom = (typeof recordFn.addCustomEvent === 'function')
          ? recordFn.addCustomEvent
          : (typeof rrwebRecord !== 'undefined' && typeof rrwebRecord.addCustomEvent === 'function')
            ? rrwebRecord.addCustomEvent
            : null;
        if (addCustom) {
          addCustom("krama:epoch", {
            wall_time_ms: Date.now(),
            perf_time_ms: typeof performance !== 'undefined' ? Math.round(performance.now()) : 0,
            doc_id: docId
          });
        }
      } catch (e) {
        // Custom anchor event optional
      }
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

    @property
    def artifact_store(self) -> ArtifactStore | None:
        """Underlying ArtifactStore port dependency if configured."""
        ...

    @property
    def recording_start_epoch_ms(self) -> int | None:
        """Baseline epoch timestamp in integer milliseconds when recording started."""
        ...

    def get_relative_ms(self, epoch_ms: int) -> int:
        """Return milliseconds elapsed from recording baseline to epoch_ms (clamped to >= 0)."""
        ...

    async def start(self, target: BrowserContext | Page) -> None:
        """Start session recording on a browser context or page."""
        ...

    async def stop(self) -> list[dict[str, Any]]:
        """Stop session recording and return collected events."""
        ...

    async def stop_and_save(
        self,
        run_id: str | None = None,
        *,
        artifact_store: ArtifactStore | None = None,
    ) -> str:
        """Stop session recording and persist events to the artifact store."""
        ...

    def get_events(self) -> list[dict[str, Any]]:
        """Return all recorded events collected so far."""
        ...

    def save_to_json(
        self,
        file_path: Path | str,
        *,
        indent: int | None = None,
        compress_gzip: bool = False,
    ) -> Path:
        """Save accumulated events to a JSON file (optionally gzip compressed)."""
        ...


async def _persist_to_store(
    store: ArtifactStore | Any,
    key: str,
    data: bytes,
    content_type: str,
) -> str:
    """Persist data to an ArtifactStore via save() or put()."""
    if hasattr(store, "save"):
        call_fn = store.save
    elif hasattr(store, "put"):
        call_fn = store.put
    else:
        raise AttributeError("Artifact store must implement save() or put()")

    res = call_fn(key=key, data=data, content_type=content_type)
    if inspect.isawaitable(res):
        res = await res

    if isinstance(res, str) and res:
        return res
    if hasattr(res, "key") and isinstance(res.key, str):
        return res.key
    if hasattr(res, "path") and isinstance(res.path, str):
        return res.path
    return key

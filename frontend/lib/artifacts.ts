// One place that turns a screenshot reference from the API into a URL the browser can load.
//
// The backend uses two shapes (docs/api-contract.md):
// - SSE events (`step.action_done` / `step.failed` `screenshot_url`) carry a PATH: `/api/v1/artifacts/runs/...`.
//   It is relative to the API origin, NOT the Next.js origin, so it must be prefixed with the API origin.
// - Workflow steps (`screenshot_path`, `observed_state.screenshot_path`) carry a bare artifact KEY:
//   `runs/<run>/step-1.png`, served at `${apiBase}/artifacts/${key}`.
// Mock fixtures use app-relative paths (`/screenshots/step-1.png`, served from `public/`), which stay as they are.

export const DEFAULT_API_URL = "http://localhost:8000/api/v1";

export function normalizeBaseUrl(url?: string): string {
  const raw = (url || process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).trim();
  const cleaned = raw.replace(/\/+$/, "");
  if (cleaned === "http://localhost:8000" || cleaned === "http://127.0.0.1:8000") {
    return `${cleaned}/api/v1`;
  }
  return cleaned;
}

/** The configured API base, e.g. `http://localhost:8000/api/v1`. */
export function apiBaseUrl(): string {
  return normalizeBaseUrl(process.env.NEXT_PUBLIC_API_URL);
}

/**
 * Resolves a screenshot reference to a loadable URL, or `undefined` when there is none.
 * - absolute URLs (`http:`, `https:`, `data:`, `blob:`) are returned unchanged
 * - `/api/...` paths get the API origin in front
 * - other `/...` paths are app-relative (mock fixtures in `public/`) and are returned unchanged
 * - anything else is a bare artifact key: `${apiBase}/artifacts/${key}`
 */
export function artifactUrl(ref: string | null | undefined, apiBase: string = apiBaseUrl()): string | undefined {
  if (!ref) return undefined;
  const value = ref.trim();
  if (!value) return undefined;
  if (/^(https?:|data:|blob:)/i.test(value)) return value;
  const base = apiBase.replace(/\/+$/, "");
  if (value.startsWith("/api/")) {
    return `${new URL(base).origin}${value}`;
  }
  if (value.startsWith("/")) return value;
  const key = value
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${base}/artifacts/${key}`;
}

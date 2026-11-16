"use client";

import type { LiveScreenshotFrame } from "@/hooks/useRunStream";

export interface LiveViewportStreamProps {
  frame: LiveScreenshotFrame | null;
  targetUrl?: string;
  isLoading?: boolean;
  className?: string;
}

export function LiveViewportStream({
  frame,
  targetUrl,
  isLoading = false,
  className = "",
}: LiveViewportStreamProps) {
  const formattedTime = frame?.timestampMs
    ? new Date(frame.timestampMs).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  return (
    <div
      data-testid="live-viewport-stream"
      className={`kr-spectrum-border flex flex-col overflow-hidden rounded-3xl bg-ink-950 ${className}`}
    >
      {/* Viewport Header */}
      <div className="flex items-center justify-between rounded-t-3xl border-b border-white/10 bg-ink-900/90 px-4 py-2.5 backdrop-blur-md">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5">
            <span
              data-testid="live-dot"
              className="kr-dot kr-dot-live kr-verify !size-2"
            />
            <span
              data-testid="live-indicator-badge"
              className="kr-chip kr-verify !py-0.5 !text-[10px] uppercase tracking-[0.2em]"
            >
              LIVE HEADLESS
            </span>
          </div>

          {targetUrl && (
            <span
              data-testid="stream-target-url"
              className="max-w-xs truncate rounded-full bg-white/5 px-3 py-0.5 font-mono text-xs text-run sm:max-w-md"
            >
              {targetUrl}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0 text-[11px] text-ink-400">
          {formattedTime && (
            <span data-testid="stream-timestamp" className="font-mono text-plan">
              {formattedTime}
            </span>
          )}
        </div>
      </div>

      {/* Screen Frame or Skeleton Loader */}
      <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-b-3xl bg-ink-900/50">
        {/* neon monitor: a slow scanline and soft vignette over the live frame */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 z-10 h-1/3 animate-[kr-scan_4s_linear_infinite] bg-gradient-to-b from-transparent via-run/10 to-transparent" />
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 shadow-[inset_0_0_80px_rgba(0,0,0,0.6)]" />
        {isLoading || !frame ? (
          <div
            data-testid="viewport-skeleton"
            className="kr-grid-bg flex size-full flex-col items-center justify-center gap-3 bg-ink-900 p-8 text-center"
          >
            <div className="size-12 animate-spin rounded-full border-4 border-white/10 border-t-run shadow-[0_0_30px_-4px_var(--run)]" />
            <div className="space-y-1">
              <p className="font-mono text-xs font-semibold text-run">
                Waiting for browser viewport frame…
              </p>
              <p className="text-[11px] text-ink-400">
                Live headless screenshots will render here as the agent acts
              </p>
            </div>
          </div>
        ) : (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={frame.imageUrl}
            alt="Headless browser live stream"
            data-testid="live-stream-image"
            className="size-full object-contain"
          />
        )}
      </div>
    </div>
  );
}

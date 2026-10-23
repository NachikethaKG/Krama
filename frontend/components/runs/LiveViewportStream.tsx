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
      className={`flex flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-950 shadow-sm dark:border-zinc-800 ${className}`}
    >
      {/* Viewport Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/90 px-4 py-2.5 backdrop-blur-md">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5">
            <span
              data-testid="live-dot"
              className="size-2 rounded-full bg-emerald-500 animate-pulse"
            />
            <span
              data-testid="live-indicator-badge"
              className="rounded bg-emerald-950/80 px-2 py-0.5 text-[10px] font-bold tracking-wider text-emerald-400 uppercase ring-1 ring-inset ring-emerald-500/20"
            >
              LIVE HEADLESS
            </span>
          </div>

          {targetUrl && (
            <span
              data-testid="stream-target-url"
              className="text-xs font-mono text-zinc-400 truncate max-w-xs sm:max-w-md"
            >
              {targetUrl}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0 text-[11px] text-zinc-400">
          {formattedTime && (
            <span data-testid="stream-timestamp" className="font-mono">
              {formattedTime}
            </span>
          )}
        </div>
      </div>

      {/* Screen Frame or Skeleton Loader */}
      <div className="relative flex aspect-video w-full items-center justify-center bg-zinc-900/50">
        {isLoading || !frame ? (
          <div
            data-testid="viewport-skeleton"
            className="flex size-full flex-col items-center justify-center gap-3 p-8 text-center animate-pulse bg-zinc-900"
          >
            <div className="size-10 rounded-full border-2 border-zinc-700 border-t-zinc-400 animate-spin" />
            <div className="space-y-1">
              <p className="text-xs font-semibold text-zinc-400">
                Waiting for browser viewport frame…
              </p>
              <p className="text-[11px] text-zinc-600">
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

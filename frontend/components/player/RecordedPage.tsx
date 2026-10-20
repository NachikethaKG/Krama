"use client";

import { useEffect, useRef, useState } from "react";
import type { eventWithTime } from "@rrweb/types";

export interface RecordedPageProps {
  /** The workflow's rrweb recording (GET /api/v1/artifacts/<recording_path>). */
  events: eventWithTime[];
  /** Milliseconds since the recording's first event: the moment to show (workflow_steps.start_ms/end_ms). */
  timeOffsetMs: number;
  viewport: { width: number; height: number };
}

interface ReplayerLike {
  pause(timeOffset?: number): void;
  destroy(): void;
  wrapper: HTMLDivElement;
  iframe: HTMLIFrameElement;
}

/**
 * The real page from the run's rrweb recording, frozen at `timeOffsetMs`: the tutorial's backdrop, so the
 * learner sees the actual UI (docs/architecture.md: real UI capture, never generated UI).
 *
 * It renders at the recording's viewport size in CSS px, the same space as the step bboxes, so overlays drawn
 * on top line up after subtracting the step's scroll. It is never interactive: the tutorial controls it.
 */
export function RecordedPage({ events, timeOffsetMs, viewport }: RecordedPageProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const replayerRef = useRef<ReplayerLike | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // rrweb touches `window`, so it is loaded in the browser only, once per recording.
  useEffect(() => {
    const root = rootRef.current;
    if (!root || events.length < 2) return;
    let cancelled = false;
    import("rrweb")
      .then(({ Replayer }) => {
        if (cancelled) return;
        const replayer = new Replayer(events, {
          root,
          mouseTail: false,
          showWarning: false,
          skipInactive: false,
          triggerFocus: false,
          UNSAFE_replayCanvas: false,
        }) as unknown as ReplayerLike;
        replayer.wrapper.style.pointerEvents = "none";
        replayer.iframe.style.border = "0"; // a default border would shift the page against the overlays
        replayerRef.current = replayer;
        setReady(true);
      })
      .catch(() => setFailed(true));
    return () => {
      cancelled = true;
      replayerRef.current?.destroy();
      replayerRef.current = null;
      setReady(false);
      root.replaceChildren();
    };
  }, [events]);

  useEffect(() => {
    if (ready) replayerRef.current?.pause(Math.max(0, timeOffsetMs));
  }, [ready, timeOffsetMs]);

  return (
    <div
      data-testid="recorded-page"
      data-ready={ready ? "true" : "false"}
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden bg-white"
      style={{ width: viewport.width, height: viewport.height }}
    >
      <div ref={rootRef} className="krama-replay-root" />
      {failed && (
        <p className="absolute inset-0 flex items-center justify-center text-sm text-zinc-500">
          The recording could not be shown.
        </p>
      )}
    </div>
  );
}

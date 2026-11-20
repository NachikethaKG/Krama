"use client";

import { useEffect, useRef, useState } from "react";
import type { HandBackDone, TakeoverInput } from "@krama/contracts-ts";
import { Hand, Loader2, MonitorPlay, ShieldAlert } from "lucide-react";
import { type ApiClient, type TakeoverServerMessage, errorMessage } from "@/lib/api";

const WIDTH = 1280;
const HEIGHT = 800;
const MOVE_EVERY_MS = 40;

/** Keys the page should get instead of the browser (scrolling, tab focus, form submit). */
const KEPT_KEYS = new Set(["Tab", "Enter", "Backspace", "Delete", "Escape", " ", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "PageUp", "PageDown", "Home", "End"]);

export interface TakeoverViewerProps {
  runId: string;
  stepSeq: number;
  client: ApiClient;
  /** The takeover ended (handed back, idle, closed): the live view returns to the pause. */
  onEnded: () => void;
}

const HAND_BACK: { done: HandBackDone; label: string; detail: string }[] = [
  { done: "barrier", label: "I cleared what was in the way", detail: "Krama checks the page and does the step itself." },
  { done: "step", label: "I did this step", detail: "Krama checks the step worked, then goes on." },
  { done: "rest", label: "I finished the task", detail: "Krama checks the end result." },
];

/** Modifier flags for the contract's TakeoverModifiers. */
function modifiers(e: { altKey: boolean; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }) {
  return { alt: e.altKey, ctrl: e.ctrlKey, meta: e.metaKey, shift: e.shiftKey };
}

/**
 * Human takeover (#411, ADR 0008): the paused run's live page, which the owner drives with mouse, keyboard and
 * paste, then hands back by saying what they did. Frames are shown and dropped, never stored.
 */
export function TakeoverViewer({ runId, stepSeq, client, onEnded }: TakeoverViewerProps) {
  const [frame, setFrame] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [ended, setEnded] = useState<TakeoverServerMessage["reason"] | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const screen = useRef<ReturnType<ApiClient["openScreen"]> | null>(null);
  const surface = useRef<HTMLDivElement | null>(null);
  const lastMove = useRef(0);

  useEffect(() => {
    const connection = client.openScreen(runId);
    screen.current = connection;
    connection.onFrame(setFrame);
    connection.onMessage((message) => {
      if (message.type === "blocked") setNotice(message.message ?? "That was blocked during the takeover.");
      if (message.type === "ended") setEnded(message.reason ?? "closed");
    });
    connection.onClose((code) => {
      if (code === 4403) setError("You can't control this run.");
      else if (code === 4409) setError("Someone else is already controlling this run, or the takeover ended.");
      setEnded((current) => current ?? "closed");
    });
    surface.current?.focus();
    return () => {
      connection.close();
      screen.current = null;
    };
  }, [client, runId]);

  const send = (input: TakeoverInput) => screen.current?.send(input);

  const point = (e: React.MouseEvent | React.WheelEvent) => {
    const box = e.currentTarget.getBoundingClientRect();
    const x = Math.min(WIDTH, Math.max(0, ((e.clientX - box.left) * WIDTH) / box.width));
    const y = Math.min(HEIGHT, Math.max(0, ((e.clientY - box.top) * HEIGHT) / box.height));
    return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 };
  };

  const button = (b: number) => (b === 1 ? "middle" : b === 2 ? "right" : "left") as "left" | "middle" | "right";

  const handBack = async (done: HandBackDone) => {
    setSending(true);
    setError(null);
    try {
      await client.handBack(runId, stepSeq, done);
      onEnded();
    } catch (err) {
      setError(errorMessage(err, "Handing back failed."));
      setSending(false);
    }
  };

  if (ended && ended !== "handed_back") {
    return (
      <div data-testid="takeover-ended" role="status" className="kr-tone-card rounded-3xl p-4 text-sm text-ink-200">
        <p className="font-semibold text-white">
          {ended === "idle" ? "The takeover ended after 5 minutes without input." : "The takeover ended."}
        </p>
        <p className="mt-1 text-ink-300">{error ?? "The run is still paused: take over again, allow or cancel it."}</p>
        <button type="button" onClick={onEnded} className="kr-btn kr-btn-ghost mt-3 px-3.5 py-1.5 text-xs">
          Back to the pause
        </button>
      </div>
    );
  }

  return (
    <section data-testid="takeover-viewer" aria-label="Live page you control" className="kr-tone-card rounded-3xl p-4">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-semibold text-white">
          <MonitorPlay aria-hidden="true" className="size-4 text-run" />
          You control the page at step {stepSeq}
        </p>
        <button
          type="button"
          data-testid="takeover-done-btn"
          onClick={() => setChoosing(true)}
          className="kr-btn kr-btn-tone px-3.5 py-1.5 text-xs"
        >
          <Hand aria-hidden="true" className="size-3.5" />
          I&apos;m done
        </button>
      </header>

      <p className="mb-2 flex items-start gap-2 text-xs text-ink-300">
        <ShieldAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-plan" />
        What you type goes to the page only; Krama never stores the screen. Only this site and its sign-in pages open
        here.
      </p>

      <div
        ref={surface}
        data-testid="takeover-surface"
        tabIndex={0}
        role="application"
        aria-label="The run's page. Click to focus, then use mouse and keyboard as usual."
        className="relative aspect-[16/10] w-full cursor-default overflow-hidden rounded-2xl border border-ink-700 bg-ink-950 outline-none focus:border-run"
        onContextMenu={(e) => e.preventDefault()}
        onMouseDown={(e) => {
          surface.current?.focus();
          send({ type: "mouse", event: "down", ...point(e), button: button(e.button), click_count: Math.min(3, e.detail || 1) });
        }}
        onMouseUp={(e) =>
          send({ type: "mouse", event: "up", ...point(e), button: button(e.button), click_count: Math.min(3, e.detail || 1) })
        }
        onMouseMove={(e) => {
          const now = Date.now();
          if (now - lastMove.current < MOVE_EVERY_MS) return;
          lastMove.current = now;
          send({ type: "mouse", event: "move", ...point(e) });
        }}
        onWheel={(e) => send({ type: "mouse", event: "wheel", ...point(e), delta_x: e.deltaX, delta_y: e.deltaY })}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v") return; // the paste event sends the text
          if (KEPT_KEYS.has(e.key) || e.key.length === 1 || e.ctrlKey || e.metaKey) e.preventDefault();
          send({ type: "key", event: "down", key: e.key.slice(0, 32), code: e.code.slice(0, 32), modifiers: modifiers(e) });
        }}
        onKeyUp={(e) => send({ type: "key", event: "up", key: e.key.slice(0, 32), code: e.code.slice(0, 32), modifiers: modifiers(e) })}
        onPaste={(e) => {
          e.preventDefault();
          const text = e.clipboardData.getData("text/plain").slice(0, 4000);
          if (text) send({ type: "text", text });
        }}
      >
        {frame ? (
          // eslint-disable-next-line @next/next/no-img-element -- a live frame (object URL), not a static asset
          <img data-testid="takeover-frame" src={frame} alt="" draggable={false} className="size-full select-none object-contain" />
        ) : (
          <p className="flex size-full items-center justify-center gap-2 text-sm text-ink-300">
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            Connecting to the page…
          </p>
        )}
      </div>

      {notice ? (
        <p role="status" data-testid="takeover-notice" className="mt-2 text-xs font-semibold text-plan">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" data-testid="takeover-error" className="mt-2 text-xs font-semibold text-danger">
          {error}
        </p>
      ) : null}

      {choosing ? (
        <div data-testid="takeover-handback" role="group" aria-label="What did you do?" className="mt-3 grid gap-2 sm:grid-cols-3">
          {HAND_BACK.map((option) => (
            <button
              key={option.done}
              type="button"
              data-testid={`handback-${option.done}`}
              disabled={sending}
              onClick={() => handBack(option.done)}
              className="rounded-2xl border border-ink-700 bg-ink-950/60 p-3 text-left text-xs text-ink-300 transition-colors hover:border-run"
            >
              <span className="block text-sm font-semibold text-white">{option.label}</span>
              {option.detail}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

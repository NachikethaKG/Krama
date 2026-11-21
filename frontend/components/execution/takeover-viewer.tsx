"use client";

import { useEffect, useRef, useState } from "react";
import type { HandBackDone, TakeoverInput } from "@krama/contracts-ts";
import { Hand, Loader2, MonitorPlay, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
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

/** Label and detail of each choice: handBack.<done>.label / .detail in the "takeover" namespace. */
const HAND_BACK: HandBackDone[] = ["barrier", "step", "rest"];

/** Text from the server is shown as-is; our own text is a message key, translated when rendered. */
type Text = { key: string } | { text: string };

/** Modifier flags for the contract's TakeoverModifiers. */
function modifiers(e: { altKey: boolean; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }) {
  return { alt: e.altKey, ctrl: e.ctrlKey, meta: e.metaKey, shift: e.shiftKey };
}

/**
 * Human takeover (#411, ADR 0008): the paused run's live page, which the owner drives with mouse, keyboard and
 * paste, then hands back by saying what they did. Frames are shown and dropped, never stored.
 */
export function TakeoverViewer({ runId, stepSeq, client, onEnded }: TakeoverViewerProps) {
  const t = useTranslations("takeover");
  const show = (m: Text) => ("key" in m ? t(m.key) : m.text);
  const [frame, setFrame] = useState<string | null>(null);
  const [notice, setNotice] = useState<Text | null>(null);
  const [ended, setEnded] = useState<TakeoverServerMessage["reason"] | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<Text | null>(null);
  const screen = useRef<ReturnType<ApiClient["openScreen"]> | null>(null);
  const surface = useRef<HTMLDivElement | null>(null);
  const lastMove = useRef(0);

  useEffect(() => {
    const connection = client.openScreen(runId);
    screen.current = connection;
    // A connection this effect already closed must not touch the view: React runs effects twice in dev, and
    // the first socket's close used to show "the takeover ended" over the live one (#431 gate).
    let live = true;
    connection.onFrame((url) => live && setFrame(url));
    connection.onMessage((message) => {
      if (!live) return;
      if (message.type === "blocked") setNotice(message.message ? { text: message.message } : { key: "blocked" });
      if (message.type === "ended") setEnded(message.reason ?? "closed");
    });
    connection.onClose((code) => {
      if (!live) return;
      if (code === 4403) setError({ key: "forbidden" });
      else if (code === 4409) setError({ key: "conflict" });
      setEnded((current) => current ?? "closed");
    });
    surface.current?.focus();
    return () => {
      live = false;
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
      setError({ text: errorMessage(err, t("handBackFailed")) });
      setSending(false);
    }
  };

  if (ended && ended !== "handed_back") {
    return (
      <div data-testid="takeover-ended" role="status" className="kr-tone-card rounded-3xl p-4 text-sm text-ink-200">
        <p className="font-semibold text-white">
          {ended === "idle" ? t("endedIdle") : t("ended")}
        </p>
        <p className="mt-1 text-ink-300">{error ? show(error) : t("stillPaused")}</p>
        <button type="button" onClick={onEnded} className="kr-btn kr-btn-ghost mt-3 px-3.5 py-1.5 text-xs">
          {t("backToPause")}
        </button>
      </div>
    );
  }

  return (
    <section data-testid="takeover-viewer" aria-label={t("sectionAria")} className="kr-tone-card rounded-3xl p-4">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-semibold text-white">
          <MonitorPlay aria-hidden="true" className="size-4 text-run" />
          {t("youControl", { seq: stepSeq })}
        </p>
        <button
          type="button"
          data-testid="takeover-done-btn"
          onClick={() => setChoosing(true)}
          className="kr-btn kr-btn-tone px-3.5 py-1.5 text-xs"
        >
          <Hand aria-hidden="true" className="size-3.5" />
          {t("done")}
        </button>
      </header>

      <p className="mb-2 flex items-start gap-2 text-xs text-ink-300">
        <ShieldAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-plan" />
        {t("privacy")}
      </p>

      <div
        ref={surface}
        data-testid="takeover-surface"
        tabIndex={0}
        role="application"
        aria-label={t("surfaceAria")}
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
            {t("connecting")}
          </p>
        )}
      </div>

      {notice ? (
        <p role="status" data-testid="takeover-notice" className="mt-2 text-xs font-semibold text-plan">
          {show(notice)}
        </p>
      ) : null}
      {error ? (
        <p role="alert" data-testid="takeover-error" className="mt-2 text-xs font-semibold text-danger">
          {show(error)}
        </p>
      ) : null}

      {choosing ? (
        <div data-testid="takeover-handback" role="group" aria-label={t("handBackAria")} className="mt-3 grid gap-2 sm:grid-cols-3">
          {HAND_BACK.map((done) => (
            <button
              key={done}
              type="button"
              data-testid={`handback-${done}`}
              disabled={sending}
              onClick={() => handBack(done)}
              className="rounded-2xl border border-ink-700 bg-ink-950/60 p-3 text-left text-xs text-ink-300 transition-colors hover:border-run"
            >
              <span className="block text-sm font-semibold text-white">{t(`handBack.${done}.label`)}</span>
              {t(`handBack.${done}.detail`)}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Check, Lock, MousePointer2 } from "lucide-react";

/**
 * The hero's "watch it work" window: a pretend browser where a cursor glides to each control, clicks,
 * and evidence chips light up as every step is verified. Decorative (aria-hidden): the page copy says
 * the same thing in words.
 */
const STEPS = [
  { label: "Click “New repository”", target: { x: 76, y: 14 }, evidence: ["url", "aria"], tone: "var(--plan)" },
  { label: "Type “bench-new-4821”", target: { x: 38, y: 40 }, evidence: ["field value"], tone: "var(--approve)" },
  { label: "Choose “Private”", target: { x: 22, y: 60 }, evidence: ["checked"], tone: "var(--run)" },
  { label: "Click “Create repository”", target: { x: 30, y: 82 }, evidence: ["url", "network 3xx"], tone: "var(--verify)" },
];

const STEP_MS = 2200;

export function HeroRunDemo() {
  const [index, setIndex] = useState(0);
  const [clicked, setClicked] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const click = setTimeout(() => setClicked(true), STEP_MS * 0.45);
    const next = setTimeout(() => {
      setClicked(false);
      setIndex((i) => (i + 1) % STEPS.length);
    }, STEP_MS);
    return () => {
      clearTimeout(click);
      clearTimeout(next);
    };
  }, [index]);

  const step = STEPS[index];

  return (
    <div aria-hidden="true" className="kr-spectrum-border kr-float relative rounded-3xl bg-ink-900/90 p-3 shadow-2xl">
      {/* window chrome */}
      <div className="flex items-center gap-2 px-2 pb-3">
        <span className="size-3 rounded-full bg-danger" />
        <span className="size-3 rounded-full bg-plan" />
        <span className="size-3 rounded-full bg-verify" />
        <div className="ml-3 flex flex-1 items-center gap-2 rounded-full bg-white/5 px-3 py-1 font-mono text-[11px] text-ink-300">
          <Lock className="size-3 text-verify" />
          github.com/new
        </div>
        <span className="kr-chip kr-run ml-2 !py-0.5 !text-[10px]">
          <span className="kr-dot kr-dot-live !size-1.5" /> LIVE
        </span>
      </div>

      {/* fake page */}
      <div className="relative h-64 overflow-hidden rounded-2xl bg-gradient-to-br from-ink-850 to-ink-800 sm:h-72">
        <div className="absolute left-[6%] top-[8%] h-3 w-1/3 rounded bg-white/15" />
        <div
          className="absolute right-[6%] top-[8%] rounded-lg px-3 py-1.5 text-[10px] font-bold text-oncolor"
          style={{ background: "var(--plan)" }}
        >
          New repository
        </div>
        <div className="absolute left-[6%] top-[33%] h-8 w-[64%] rounded-lg border border-white/15 bg-white/5 px-3 pt-2 font-mono text-[11px] text-white/80">
          {index >= 1 ? "bench-new-4821" : ""}
          {index === 1 && <span className="kr-caret" />}
        </div>
        <div className="absolute left-[6%] top-[55%] flex items-center gap-2 text-[11px] text-ink-300">
          <span
            className="flex size-4 items-center justify-center rounded-full border border-white/30"
            style={index >= 2 ? { background: "var(--run)", borderColor: "var(--run)" } : undefined}
          >
            {index >= 2 && <span className="size-1.5 rounded-full bg-ink-950" />}
          </span>
          Private
        </div>
        <div className="absolute left-[6%] top-[76%] rounded-lg bg-verify px-3 py-1.5 text-[10px] font-bold text-oncolor">
          Create repository
        </div>

        {/* highlight around the target */}
        <div
          className="absolute size-16 -translate-x-1/2 -translate-y-1/2 rounded-2xl border-2 transition-all duration-700"
          style={{
            left: `${step.target.x}%`,
            top: `${step.target.y}%`,
            borderColor: step.tone,
            boxShadow: `0 0 30px ${step.tone}`,
          }}
        />
        {/* click ripple */}
        {clicked && (
          <span
            className="absolute size-10 -translate-x-1/2 -translate-y-1/2 animate-ping rounded-full"
            style={{ left: `${step.target.x}%`, top: `${step.target.y}%`, background: step.tone, opacity: 0.5 }}
          />
        )}
        {/* cursor */}
        <MousePointer2
          className="absolute size-6 fill-white text-oncolor drop-shadow-[0_4px_10px_rgba(0,0,0,0.6)] transition-all duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{ left: `${step.target.x + 1}%`, top: `${step.target.y + 2}%` }}
        />
        {/* scan line */}
        <div className="pointer-events-none absolute inset-x-0 h-1/3 animate-[kr-scan_3.5s_linear_infinite] bg-gradient-to-b from-transparent via-run/10 to-transparent" />
      </div>

      {/* step + evidence */}
      <div className="mt-3 flex flex-wrap items-center gap-2 px-1">
        <span className="font-mono text-[11px] text-ink-400">step {index + 1}/4</span>
        <span className="text-sm font-semibold text-white">{step.label}</span>
        <span className="ml-auto flex gap-1.5">
          {step.evidence.map((e) => (
            <span
              key={e}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold text-oncolor transition-opacity duration-300"
              style={{ background: "var(--verify)", opacity: clicked ? 1 : 0.15 }}
            >
              <Check className="size-3" /> {e}
            </span>
          ))}
        </span>
      </div>
      <div className="mt-3 flex gap-1.5 px-1">
        {STEPS.map((s, i) => (
          <span
            key={s.label}
            className="h-1.5 flex-1 rounded-full transition-all duration-500"
            style={{ background: i <= index ? s.tone : "rgb(var(--fg-rgb) / 0.1)", boxShadow: i === index ? `0 0 12px ${s.tone}` : undefined }}
          />
        ))}
      </div>
    </div>
  );
}

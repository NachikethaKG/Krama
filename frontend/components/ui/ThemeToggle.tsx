"use client";

import { type MouseEvent, useSyncExternalStore } from "react";
import { flushSync } from "react-dom";
import { Moon, Sun } from "lucide-react";
import { applyTheme, currentTheme, subscribeTheme, type Theme } from "@/lib/theme";

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => { ready: Promise<void> };
};

/**
 * Sun / moon switch between Krama's dark and light themes. Where the browser supports view transitions,
 * the new theme spreads out as a circle from the button; otherwise (or with reduced motion) it just swaps.
 */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const theme = useSyncExternalStore<Theme>(subscribeTheme, currentTheme, () => "dark");
  const next: Theme = theme === "dark" ? "light" : "dark";

  const toggle = (event: MouseEvent<HTMLButtonElement>) => {
    const doc = document as ViewTransitionDocument;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!doc.startViewTransition || reduced) {
      applyTheme(next);
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const transition = doc.startViewTransition(() => flushSync(() => applyTheme(next)));
    transition.ready
      .then(() => {
        document.documentElement.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 650, easing: "cubic-bezier(0.22, 1, 0.36, 1)", pseudoElement: "::view-transition-new(root)" },
        );
      })
      .catch(() => undefined);
  };

  const label = next === "light" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      data-testid="theme-toggle"
      data-theme-current={theme}
      className={`kr-btn kr-btn-ghost relative size-9 shrink-0 overflow-hidden !p-0 ${
        theme === "dark" ? "kr-plan" : "kr-approve"
      } ${className}`}
    >
      <Sun
        aria-hidden="true"
        className={`absolute size-4 text-plan transition-all duration-500 ${
          theme === "dark" ? "rotate-0 scale-100 opacity-100" : "-rotate-90 scale-0 opacity-0"
        }`}
      />
      <Moon
        aria-hidden="true"
        className={`absolute size-4 text-approve transition-all duration-500 ${
          theme === "light" ? "rotate-0 scale-100 opacity-100" : "rotate-90 scale-0 opacity-0"
        }`}
      />
    </button>
  );
}

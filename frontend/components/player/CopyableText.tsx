"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

export interface CopyableTextProps {
  text: string;
  label?: string;
  className?: string;
  code?: boolean;
}

export function CopyableText({
  text,
  label,
  className = "",
  code = true,
}: CopyableTextProps) {
  const t = useTranslations("player");
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    let success = false;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        success = true;
      }
    } catch {
      // Fallback if clipboard API rejects
    }

    if (!success && typeof document !== "undefined") {
      try {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        success = true;
      } catch {
        success = false;
      }
    }

    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [text]);

  return (
    <div
      className={`group flex items-center justify-between gap-2 rounded-2xl border border-white/10 bg-ink-950/60 px-3 py-1 text-xs text-ink-300 transition-all hover:border-learn/50 hover:shadow-[0_0_20px_-8px_var(--learn)] ${className}`}
    >
      <div className="flex min-w-0 items-center gap-2">
        {label && (
          <span className="shrink-0 font-bold uppercase tracking-wider text-[10px] text-learn">
            {label}:
          </span>
        )}
        <span
          className={`truncate ${code ? "font-mono font-semibold text-white" : ""}`}
          title={text}
        >
          {text}
        </span>
      </div>

      <button
        type="button"
        onClick={handleCopy}
        data-testid="copy-button"
        aria-label={copied ? t("copyable.copiedAria") : t("copyable.copyAria", { text })}
        className="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center gap-1.5 rounded-xl px-2.5 py-2 text-xs font-bold text-ink-300 transition-colors hover:bg-white/10 hover:text-white"
      >
        {copied ? (
          <>
            <svg
              className="h-3.5 w-3.5 text-verify"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-verify">{t("copyable.copied")}</span>
          </>
        ) : (
          <>
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
            <span>{t("copyable.copy")}</span>
          </>
        )}
      </button>
    </div>
  );
}

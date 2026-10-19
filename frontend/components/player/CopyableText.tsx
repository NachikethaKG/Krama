"use client";

import { useCallback, useState } from "react";

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
      className={`group flex items-center justify-between gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs text-zinc-800 transition-colors dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200 ${className}`}
    >
      <div className="flex min-w-0 items-center gap-2">
        {label && (
          <span className="shrink-0 font-medium text-zinc-500 dark:text-zinc-400">
            {label}:
          </span>
        )}
        <span
          className={`truncate ${code ? "font-mono font-medium text-zinc-900 dark:text-zinc-100" : ""}`}
          title={text}
        >
          {text}
        </span>
      </div>

      <button
        type="button"
        onClick={handleCopy}
        data-testid="copy-button"
        aria-label={copied ? "Copied to clipboard" : `Copy ${text} to clipboard`}
        className="flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-zinc-600 hover:bg-zinc-200 hover:text-zinc-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      >
        {copied ? (
          <>
            <svg
              className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-emerald-600 dark:text-emerald-400">Copied!</span>
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
            <span>Copy</span>
          </>
        )}
      </button>
    </div>
  );
}

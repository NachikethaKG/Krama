import React from "react";

export interface OutdatedSiteBannerProps {
  className?: string;
  message?: string;
}

export function OutdatedSiteBanner({
  className = "",
  message = "The target website has changed since this tutorial was recorded. Some steps, locators, or flows may no longer match the current site.",
}: OutdatedSiteBannerProps) {
  return (
    <div
      role="alert"
      data-testid="outdated-site-banner"
      className={`rounded-xl border border-amber-300 bg-amber-50/90 p-4 shadow-sm dark:border-amber-700/80 dark:bg-amber-950/50 ${className}`}
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 rounded-lg bg-amber-100 p-2 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300">
          <svg
            className="size-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-amber-900 dark:text-amber-100">
              Site Changed
            </h3>
            <span className="rounded-full bg-amber-200/80 px-2 py-0.5 text-[10px] font-semibold text-amber-900 dark:bg-amber-900 dark:text-amber-200">
              Outdated
            </span>
          </div>
          <p className="mt-1 text-xs text-amber-800 dark:text-amber-200/90 leading-relaxed">
            {message}
          </p>
        </div>
      </div>
    </div>
  );
}

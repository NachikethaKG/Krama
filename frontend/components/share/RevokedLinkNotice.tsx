import Link from "next/link";

export interface RevokedLinkNoticeProps {
  status?: number;
  message?: string;
}

export function RevokedLinkNotice({
  status = 404,
  message = "This tutorial link is invalid or has been revoked by the creator.",
}: RevokedLinkNoticeProps) {
  return (
    <div
      data-testid="revoked-link-notice"
      className="flex min-h-[60vh] w-full flex-col items-center justify-center px-4 py-16 text-center"
    >
      <div className="mx-auto flex max-w-md flex-col items-center rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400">
          <svg
            className="size-6"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth="1.75"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636"
            />
          </svg>
        </div>

        <span className="mb-1 text-xs font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400">
          {status === 404 ? "Link Not Found (404)" : `Unavailable (${status})`}
        </span>

        <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          Tutorial Link Unavailable
        </h1>

        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          {message}
        </p>

        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-500">
          This tutorial may have been removed, or the share link was revoked by the creator.
        </p>

        <div className="mt-6 flex items-center gap-3">
          <Link
            href="/"
            data-testid="revoked-home-link"
            className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors"
          >
            Return to Homepage
          </Link>
        </div>
      </div>
    </div>
  );
}

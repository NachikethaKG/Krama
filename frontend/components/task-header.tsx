export interface TaskHeaderProps {
  prompt: string;
  targetUrl?: string | null;
  title?: string | null;
  targetApp?: string | null;
  status?: string | null;
  className?: string;
}

export function TaskHeader({
  prompt,
  targetUrl,
  title,
  targetApp,
  status,
  className = "",
}: TaskHeaderProps) {
  return (
    <header
      data-testid="task-header"
      className={`rounded-xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              Workflow Plan
            </span>
            {targetApp && (
              <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-400">
                {targetApp}
              </span>
            )}
            {status && (
              <span
                data-testid="workflow-status-badge"
                className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
              >
                {status}
              </span>
            )}
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-900 sm:text-2xl dark:text-zinc-100">
            {title || "Workflow Approval"}
          </h1>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 border-t border-zinc-100 pt-4 sm:grid-cols-2 dark:border-zinc-800">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Task Prompt
          </span>
          <p
            data-testid="task-prompt"
            className="text-sm font-medium text-zinc-800 dark:text-zinc-200"
          >
            {prompt}
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Target System URL
          </span>
          {targetUrl ? (
            <a
              data-testid="target-url"
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-mono text-blue-600 hover:underline dark:text-blue-400"
            >
              <span>{targetUrl}</span>
              <svg
                aria-hidden="true"
                className="size-3.5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                />
              </svg>
            </a>
          ) : (
            <span
              data-testid="target-url"
              className="text-sm text-zinc-400 italic dark:text-zinc-500"
            >
              No target URL configured
            </span>
          )}
        </div>
      </div>
    </header>
  );
}

import Link from "next/link";

export interface SharedPageHeaderProps {
  title?: string;
}

export function SharedPageHeader({ title }: SharedPageHeaderProps) {
  return (
    <header
      data-testid="shared-page-header"
      className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 px-4 py-3 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/80"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/"
            className="group flex items-center gap-2 shrink-0"
            aria-label="Krama home"
          >
            <div className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-xs transition-colors group-hover:bg-indigo-500">
              K
            </div>
            <span className="text-sm font-bold tracking-tight text-zinc-900 transition-colors group-hover:text-indigo-600 dark:text-zinc-100 dark:group-hover:text-indigo-400">
              Krama
            </span>
          </Link>

          <span className="text-zinc-300 dark:text-zinc-700 shrink-0">/</span>

          <span
            data-testid="shared-mode-indicator"
            className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-700/10 dark:bg-indigo-950/50 dark:text-indigo-300 dark:ring-indigo-300/20 shrink-0"
          >
            <span className="size-1.5 rounded-full bg-indigo-600 dark:bg-indigo-400" />
            Viewing shared tutorial
          </span>

          {title && (
            <>
              <span className="text-zinc-300 dark:text-zinc-700 shrink-0 hidden md:inline">·</span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate hidden md:inline max-w-sm">
                {title}
              </span>
            </>
          )}
        </div>

        {/* Note: NO profile management, NO dashboard links, NO edit or delete controls */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 hidden sm:inline">
            Read-only preview
          </span>
        </div>
      </div>
    </header>
  );
}

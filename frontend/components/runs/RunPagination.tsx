/**
 * Cursor pagination for GET /runs (newest first). The API returns an opaque `next_cursor` and no total, so the
 * page keeps a stack of cursors: "Older" follows `next_cursor`, "Newer" pops back to the previous cursor.
 */
export interface RunPaginationProps {
  /** 1-based page number (depth of the cursor stack). */
  page: number;
  pageSize: number;
  /** Runs shown on this page. */
  itemCount: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
  disabled?: boolean;
  className?: string;
}

export function RunPagination({
  page,
  pageSize,
  itemCount,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  disabled = false,
  className = "",
}: RunPaginationProps) {
  const startItem = itemCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = (page - 1) * pageSize + itemCount;

  return (
    <nav
      role="navigation"
      aria-label="Pagination Navigation"
      className={`flex flex-col sm:flex-row items-center justify-between gap-4 py-4 px-2 ${className}`}
    >
      <div data-testid="pagination-info" className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
        {itemCount === 0 ? (
          <span>No runs to display</span>
        ) : (
          <span>
            Showing <span className="font-medium text-zinc-900 dark:text-zinc-100">{startItem}</span> to{" "}
            <span className="font-medium text-zinc-900 dark:text-zinc-100">{endItem}</span> (Page{" "}
            <span data-testid="current-page-num" className="font-semibold text-zinc-900 dark:text-zinc-100">
              {page}
            </span>
            {hasNext ? ", older runs available" : ", oldest runs"})
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          data-testid="pagination-prev"
          aria-label="Newer runs"
          disabled={!hasPrevious || disabled}
          onClick={onPrevious}
          className="inline-flex items-center justify-center px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-750 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          &larr; Newer
        </button>

        <span
          data-testid="pagination-current-page"
          aria-current="page"
          className="px-3 py-1.5 text-xs sm:text-sm font-semibold rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 min-w-8 text-center"
        >
          {page}
        </span>

        <button
          type="button"
          data-testid="pagination-next"
          aria-label="Older runs"
          disabled={!hasNext || disabled}
          onClick={onNext}
          className="inline-flex items-center justify-center px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-750 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Older &rarr;
        </button>
      </div>
    </nav>
  );
}

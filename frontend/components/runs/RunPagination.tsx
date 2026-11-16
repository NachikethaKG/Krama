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
      <div data-testid="pagination-info" className="text-xs sm:text-sm text-ink-400">
        {itemCount === 0 ? (
          <span>No runs to display</span>
        ) : (
          <span>
            Showing <span className="font-medium text-white">{startItem}</span> to{" "}
            <span className="font-medium text-white">{endItem}</span> (Page{" "}
            <span data-testid="current-page-num" className="font-semibold text-white">
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
          className="kr-btn kr-btn-ghost kr-run px-4 py-1.5 text-xs sm:text-sm"
        >
          &larr; Newer
        </button>

        <span
          data-testid="pagination-current-page"
          aria-current="page"
          className="min-w-9 rounded-full bg-run px-3 py-1.5 text-center font-mono text-xs font-extrabold text-oncolor shadow-[0_0_18px_-4px_var(--run)] sm:text-sm"
        >
          {page}
        </span>

        <button
          type="button"
          data-testid="pagination-next"
          aria-label="Older runs"
          disabled={!hasNext || disabled}
          onClick={onNext}
          className="kr-btn kr-btn-ghost kr-run px-4 py-1.5 text-xs sm:text-sm"
        >
          Older &rarr;
        </button>
      </div>
    </nav>
  );
}

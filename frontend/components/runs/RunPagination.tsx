export interface RunPaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
  className?: string;
}

export function RunPagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  disabled = false,
  className = "",
}: RunPaginationProps) {
  const isFirstPage = page <= 1;
  const isLastPage = page >= totalPages;

  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <nav
      role="navigation"
      aria-label="Pagination Navigation"
      className={`flex flex-col sm:flex-row items-center justify-between gap-4 py-4 px-2 ${className}`}
    >
      <div
        data-testid="pagination-info"
        className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400"
      >
        {total === 0 ? (
          <span>No runs to display</span>
        ) : (
          <span>
            Showing <span className="font-medium text-zinc-900 dark:text-zinc-100">{startItem}</span> to{" "}
            <span className="font-medium text-zinc-900 dark:text-zinc-100">{endItem}</span> of{" "}
            <span className="font-medium text-zinc-900 dark:text-zinc-100">{total}</span> runs (Page{" "}
            <span data-testid="current-page-num" className="font-semibold text-zinc-900 dark:text-zinc-100">{page}</span> of{" "}
            <span data-testid="total-pages-num" className="font-semibold text-zinc-900 dark:text-zinc-100">{totalPages}</span>)
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          data-testid="pagination-prev"
          aria-label="Previous page"
          disabled={isFirstPage || disabled}
          onClick={() => onPageChange(page - 1)}
          className="inline-flex items-center justify-center px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-750 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <svg
            className="size-4 mr-1"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Previous
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
          aria-label="Next page"
          disabled={isLastPage || disabled}
          onClick={() => onPageChange(page + 1)}
          className="inline-flex items-center justify-center px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-750 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next
          <svg
            className="size-4 ml-1"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </nav>
  );
}

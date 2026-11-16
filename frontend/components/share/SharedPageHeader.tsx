import Link from "next/link";
import { Eye, Share2 } from "lucide-react";
import { Logo, ThemeToggle } from "@/components/ui";

export interface SharedPageHeaderProps {
  title?: string;
}

export function SharedPageHeader({ title }: SharedPageHeaderProps) {
  return (
    <header
      data-testid="shared-page-header"
      className="sticky top-3 z-40 mx-auto mt-3 w-[min(80rem,calc(100%-1.5rem))]"
    >
      <div className="kr-glass flex items-center justify-between gap-4 rounded-full px-3 py-2 pl-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="shrink-0" aria-label="Krama home">
            <Logo size={28} />
          </Link>

          <span className="shrink-0 text-ink-600">/</span>

          <span data-testid="shared-mode-indicator" className="kr-chip kr-ask shrink-0">
            <Share2 aria-hidden="true" className="size-3" />
            Viewing shared tutorial
          </span>

          {title && (
            <>
              <span className="hidden shrink-0 text-ink-600 md:inline">·</span>
              <span className="hidden max-w-sm truncate text-xs font-semibold text-white md:inline">{title}</span>
            </>
          )}
        </div>

        {/* Note: NO profile management, NO dashboard links, NO edit or delete controls */}
        <div className="flex shrink-0 items-center gap-2">
          <span className="kr-chip kr-run hidden sm:inline-flex">
            <Eye aria-hidden="true" className="size-3" />
            Read-only preview
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

import Link from "next/link";
import { Eye, Share2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { Logo, ThemeToggle } from "@/components/ui";
import type { TutorialFreshnessStatus } from "@/types/tutorial";
import { TutorialStatusBadge } from "@/components/tutorials/TutorialStatusBadge";

export interface SharedPageHeaderProps {
  title?: string;
  status?: TutorialFreshnessStatus;
}

export function SharedPageHeader({ title, status }: SharedPageHeaderProps) {
  const t = useTranslations("share");
  return (
    <header
      data-testid="shared-page-header"
      className="sticky top-3 z-40 mx-auto mt-3 w-[min(80rem,calc(100%-1.5rem))]"
    >
      <div className="kr-glass flex items-center justify-between gap-4 rounded-full px-3 py-2 pl-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="shrink-0" aria-label={t("header.home")}>
            <Logo size={28} />
          </Link>

          <span className="shrink-0 text-ink-600">/</span>

          <span data-testid="shared-mode-indicator" className="kr-chip kr-ask shrink-0">
            <Share2 aria-hidden="true" className="size-3" />
            {t("header.viewing")}
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
          {status ? (
            <TutorialStatusBadge status={status} size="sm" />
          ) : null}
          <span className="kr-chip kr-run hidden sm:inline-flex">
            <Eye aria-hidden="true" className="size-3" />
            {t("header.readOnly")}
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

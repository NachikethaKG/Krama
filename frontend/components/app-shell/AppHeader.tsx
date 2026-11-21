"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { History, LibraryBig, LogOut, ShieldAlert, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import type { User } from "@krama/contracts-ts";
import { Logo, ThemeToggle } from "@/components/ui";
import { LanguagePicker } from "./LanguagePicker";
import { type ApiClient, getApiClient } from "@/lib/api";

// `short` is shown on phones, where the full labels don't fit next to the logo and Sign out (shell.header.nav.<key>).
// Each section wears the colour of its pipeline stage: asking (pink), learning (orange), running (cyan).
const NAV: {
  href: string;
  key: "new" | "tutorials" | "reviews" | "runs";
  color: string;
  icon: LucideIcon;
  match: (p: string) => boolean;
}[] = [
  { href: "/", key: "new", color: "var(--ask)", icon: Sparkles, match: (p) => p === "/" },
  {
    href: "/tutorials",
    key: "tutorials",
    color: "var(--learn)",
    icon: LibraryBig,
    match: (p) => p.startsWith("/tutorials"),
  },
  {
    href: "/dashboard/reviews",
    key: "reviews",
    color: "var(--plan)",
    icon: ShieldAlert,
    match: (p) => p.startsWith("/dashboard/reviews"),
  },
  {
    href: "/runs",
    key: "runs",
    color: "var(--run)",
    icon: History,
    match: (p) => p.startsWith("/runs") || p.startsWith("/workflows"),
  },
];

/** The one header of every signed-in page (#318): the app's sections and the account, nothing else. */
export function AppHeader({ client }: { client?: ApiClient }) {
  const t = useTranslations("shell.header");
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [user, setUser] = useState<User | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const [reviewCount, setReviewCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .getMe()
      .then((me) => !cancelled && setUser(me))
      .catch(() => undefined); // the page itself handles a missing session

    apiClient
      .getReviewQueueCount()
      .then((res) => {
        if (!cancelled) setReviewCount(res.count);
      })
      .catch(() => undefined);

    const handleCountChange = (e: Event) => {
      const customEvent = e as CustomEvent<{ count: number }>;
      if (customEvent.detail && typeof customEvent.detail.count === "number") {
        setReviewCount(customEvent.detail.count);
      } else {
        apiClient.getReviewQueueCount().then((res) => !cancelled && setReviewCount(res.count)).catch(() => undefined);
      }
    };

    window.addEventListener("krama:review-count-changed", handleCountChange);
    return () => {
      cancelled = true;
      window.removeEventListener("krama:review-count-changed", handleCountChange);
    };
  }, [apiClient]);

  const signOut = async () => {
    setSigningOut(true);
    try {
      await apiClient.logout();
    } catch {
      // signed out locally either way
    }
    document.cookie = "krama_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    router.push("/login");
    router.refresh();
  };

  const initial = user?.email?.[0]?.toUpperCase();

  return (
    <header data-testid="app-header" className="sticky top-3 z-30 mx-auto mt-3 w-[min(72rem,calc(100%-1.5rem))]">
      <div className="kr-glass flex h-14 items-center gap-2 rounded-full px-2 pl-3 sm:gap-4">
        <Link href="/" className="flex shrink-0 items-center rounded-full" aria-label={t("homeLabel")}>
          <span className="sm:hidden">
            <Logo size={30} showWord={false} />
          </span>
          <span className="hidden sm:inline">
            <Logo size={30} />
          </span>
        </Link>
        <nav className="flex min-w-0 items-center gap-0.5 text-sm sm:gap-1" aria-label={t("mainNav")}>
          {NAV.map((item) => {
            const active = item.match(pathname);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                data-testid={item.href === "/dashboard/reviews" ? "review-queue-nav-link" : undefined}
                aria-current={active ? "page" : undefined}
                className={`group relative flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1.5 font-semibold transition-all sm:px-3.5 ${
                  active ? "text-oncolor" : "text-ink-300 hover:text-white"
                }`}
                style={
                  active
                    ? { background: item.color, boxShadow: `0 0 22px -4px ${item.color}` }
                    : undefined
                }
              >
                <Icon
                  aria-hidden="true"
                  className="hidden size-4 transition-transform group-hover:-rotate-12 sm:block"
                  style={active ? undefined : { color: item.color }}
                />
                <span className="sm:hidden">{t(`nav.${item.key}.short`)}</span>
                <span className="hidden sm:inline">{t(`nav.${item.key}.label`)}</span>
                {item.href === "/dashboard/reviews" && reviewCount !== null && (
                  reviewCount > 0 ? (
                    <span
                      data-testid="review-queue-badge"
                      aria-label={t("pendingReviews", { count: reviewCount })}
                      className="ml-1 inline-flex size-5 items-center justify-center rounded-full bg-rose-500 text-[10px] font-extrabold text-white shadow-xs"
                    >
                      {reviewCount}
                    </span>
                  ) : (
                    <span data-testid="review-queue-badge" className="hidden">0</span>
                  )
                )}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-2 text-sm">
          <LanguagePicker />
          <ThemeToggle />
          {user && (
            <span className="hidden items-center gap-2 rounded-full bg-white/5 py-1 pl-1 pr-3 sm:flex">
              <span
                aria-hidden="true"
                className="flex size-6 items-center justify-center rounded-full text-xs font-extrabold text-oncolor"
                style={{ background: "linear-gradient(135deg, var(--ask), var(--plan))" }}
              >
                {initial}
              </span>
              <span data-testid="user-email-display" className="text-xs text-ink-300">
                {user.email}
              </span>
            </span>
          )}
          <button
            type="button"
            data-testid="dashboard-logout-btn"
            onClick={signOut}
            disabled={signingOut}
            className="kr-btn kr-btn-ghost kr-danger whitespace-nowrap px-3 py-1.5 text-xs"
          >
            <LogOut aria-hidden="true" className="size-3.5" />
            {signingOut ? t("signingOut") : t("signOut")}
          </button>
        </div>
      </div>
    </header>
  );
}

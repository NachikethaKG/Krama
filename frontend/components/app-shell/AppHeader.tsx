"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { User } from "@krama/contracts-ts";
import { type ApiClient, getApiClient } from "@/lib/api";

// `short` is shown on phones, where the full labels don't fit next to the logo and Sign out.
const NAV = [
  { href: "/", label: "New tutorial", short: "New", match: (p: string) => p === "/" },
  { href: "/tutorials", label: "My tutorials", short: "Tutorials", match: (p: string) => p.startsWith("/tutorials") },
  {
    href: "/runs",
    label: "Runs",
    short: "Runs",
    match: (p: string) => p.startsWith("/runs") || p.startsWith("/workflows"),
  },
];

/** The one header of every signed-in page (#318): the app's sections and the account, nothing else. */
export function AppHeader({ client }: { client?: ApiClient }) {
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [user, setUser] = useState<User | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .getMe()
      .then((me) => !cancelled && setUser(me))
      .catch(() => undefined); // the page itself handles a missing session
    return () => {
      cancelled = true;
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

  return (
    <header
      data-testid="app-header"
      className="sticky top-0 z-30 border-b border-zinc-200 bg-white/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4 sm:gap-6 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2" aria-label="Krama home">
          <span className="flex size-7 items-center justify-center rounded-md bg-indigo-600 text-sm font-bold text-white">
            K
          </span>
          <span className="hidden font-semibold text-zinc-900 sm:inline dark:text-zinc-100">Krama</span>
        </Link>
        <nav className="flex min-w-0 items-center gap-0.5 text-sm sm:gap-1" aria-label="Main">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded-md px-2 py-1.5 font-medium transition-colors sm:px-3 ${
                  active
                    ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                    : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                }`}
              >
                <span className="sm:hidden">{item.short}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-3 text-sm">
          {user && (
            <span data-testid="user-email-display" className="hidden text-zinc-500 sm:inline dark:text-zinc-400">
              {user.email}
            </span>
          )}
          <button
            type="button"
            data-testid="dashboard-logout-btn"
            onClick={signOut}
            disabled={signingOut}
            className="whitespace-nowrap rounded-md border border-zinc-200 px-2.5 py-1.5 font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}

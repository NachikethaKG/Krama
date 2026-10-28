import type { ReactNode } from "react";
import { AppHeader } from "@/components/app-shell";

/** Every signed-in page shares one header (#318). Sign-in and public share pages live outside this group. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <AppHeader />
      <div className="flex-1">{children}</div>
    </div>
  );
}

import type { ReactNode } from "react";
import { AppHeader } from "@/components/app-shell";

/** Every signed-in page shares one header (#318). Sign-in and public share pages live outside this group. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col">
      <AppHeader />
      <div className="kr-rise flex-1 pt-4">{children}</div>
    </div>
  );
}

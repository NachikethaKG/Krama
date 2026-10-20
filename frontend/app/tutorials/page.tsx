import Link from "next/link";
import { TutorialLibrary, TutorialPlayer } from "@/components/player";
import { giteaTutorialSpecFixture } from "@/lib/fixtures";

export const metadata = {
  title: "Tutorial Player · Krama",
  description: "Interactive tutorial player driven by TutorialSpec",
};

export default function TutorialsPage() {
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900/50">
      <nav className="border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 hover:text-indigo-600 dark:hover:text-indigo-400"
            >
              ← Krama Home
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              Interactive Tutorial
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/runs"
              className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Runs History
            </Link>
          </div>
        </div>
      </nav>

      <main className="py-6">
        {/* Real API mode: the stored workflows, each a tutorial. Mock mode: the demo tutorial. */}
        {process.env.NEXT_PUBLIC_API_MODE === "http" ? (
          <TutorialLibrary />
        ) : (
          <TutorialPlayer spec={giteaTutorialSpecFixture} />
        )}
      </main>
    </div>
  );
}

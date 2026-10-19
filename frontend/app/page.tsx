import Link from "next/link";
import { ApiStatus } from "@/components/api-status";
import { TaskInput } from "@/components/task-input";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-4 py-16">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Krama</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Turn a software question into a verified, interactive tutorial built from the real UI.
        </p>
        <div className="mt-3 flex items-center gap-3">
          <Link
            href="/tutorials"
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300 dark:hover:bg-indigo-900"
          >
            <span>▶ Try Interactive Tutorial Player</span>
          </Link>
          <Link
            href="/runs"
            className="text-xs text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            Runs History →
          </Link>
        </div>
      </div>
      <ApiStatus />
      <TaskInput />
    </main>
  );
}

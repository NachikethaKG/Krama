import Link from "next/link";
import { TaskInput } from "@/components/task-input";

export default function NewRunPage() {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-900/80">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-sm dark:bg-indigo-500">
                K
              </span>
              <span className="text-xl font-bold tracking-tight text-zinc-900 dark:text-white">
                Krama
              </span>
            </Link>
          </div>
          <Link
            href="/runs"
            className="text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            ← Back to Runs
          </Link>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-6 px-4 py-12 sm:px-6">
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mb-6 flex flex-col gap-1 border-b border-zinc-100 pb-4 dark:border-zinc-800">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Create Workflow Run
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Submit a workflow task to plan, execute, and record an interactive tutorial from live browser actions.
            </p>
          </div>
          <TaskInput />
        </div>
      </main>
    </div>
  );
}

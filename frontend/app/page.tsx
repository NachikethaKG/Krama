import { ApiStatus } from "@/components/api-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">Krama</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Turn a software question into a verified, interactive tutorial built from the real UI.
      </p>
      <ApiStatus />
    </main>
  );
}

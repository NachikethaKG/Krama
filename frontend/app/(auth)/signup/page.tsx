import Link from "next/link";

export const metadata = {
  title: "Registration Access · Krama",
  description: "Public registration is currently closed for the MVP phase.",
};

export default function SignupPage() {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-6 py-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:px-10">
      <div className="mb-6 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400 mb-3 border border-amber-200 dark:border-amber-900/60">
          <svg
            className="size-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
            />
          </svg>
        </div>
        <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-2xl">
          Public Registration Closed
        </h1>
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
          To protect rate limits and shared automation runners during our early MVP evaluation phase, self-service account registration is currently gated.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950/50 space-y-3">
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-emerald-500" />
          <h2 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
            Seeded Evaluation Credentials
          </h2>
        </div>

        <p className="text-xs text-zinc-600 dark:text-zinc-400">
          Evaluators and usability test participants can sign in using the seeded test account created via the repository recipe:
        </p>

        <div className="rounded-md border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900 text-xs font-mono space-y-1">
          <div className="flex justify-between">
            <span className="text-zinc-500">Email:</span>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">demo@krama.dev</span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Password:</span>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">krama-demo-pass</span>
          </div>
          <div className="flex justify-between pt-1 border-t border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">Recipe:</span>
            <span className="text-indigo-600 dark:text-indigo-400">just seed-users</span>
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Link
          href="/login"
          data-testid="signup-login-link"
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 transition-colors"
        >
          <span>Sign In with Seeded Account</span>
          <span aria-hidden="true">→</span>
        </Link>

        <Link
          href="/"
          className="w-full flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
        >
          ← Return to Krama Home
        </Link>
      </div>
    </div>
  );
}

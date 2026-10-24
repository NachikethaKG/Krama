"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type ApiClient, errorMessage, getApiClient, isApiError } from "@/lib/api";
import type { User } from "@krama/contracts-ts";

export interface LoginFormProps {
  client?: ApiClient;
  from?: string;
  onSuccess?: (user: User) => void;
}

export function LoginForm({ client, from: propFrom, onSuccess }: LoginFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());

  const searchFrom = searchParams ? searchParams.get("from") : null;
  const rawFrom = propFrom ?? searchFrom;
  const redirectTarget =
    rawFrom && rawFrom.startsWith("/") && !rawFrom.startsWith("//")
      ? rawFrom
      : "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const user = await apiClient.login({ email, password });
      // Mock mode only: the real API sets its own HTTP-only session cookie, which the middleware checks.
      if (typeof document !== "undefined" && process.env.NEXT_PUBLIC_API_MODE !== "http") {
        document.cookie = "krama_session=demo-mock-token; path=/; max-age=86400; SameSite=Lax";
      }

      if (onSuccess) {
        onSuccess(user);
      } else {
        router.push(redirectTarget);
        router.refresh();
      }
    } catch (err) {
      if (isApiError(err, undefined, 401) || isApiError(err, "unauthorized")) {
        setError("Invalid email or password. Please try again.");
      } else {
        setError(errorMessage(err, "Invalid email or password. Please try again."));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFillDemo = () => {
    setEmail("demo@krama.dev");
    setPassword("krama-demo-pass");
    setError(null);
  };

  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-6 py-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:px-10">
      <div className="mb-6 text-center">
        <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-2xl">
          Sign in to Krama
        </h1>
        <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">
          Access your interactive tutorials, dashboard, and execution runs
        </p>
      </div>

      {error ? (
        <div
          role="alert"
          data-testid="login-error"
          className="mb-5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-400 flex items-start gap-2"
        >
          <svg
            className="size-4 shrink-0 mt-0.5 text-rose-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <span>{error}</span>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label
            htmlFor="email"
            className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300"
          >
            Email address
          </label>
          <div className="mt-1">
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              data-testid="login-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="demo@krama.dev"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-500"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300"
          >
            Password
          </label>
          <div className="mt-1">
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              data-testid="login-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-500"
            />
          </div>
        </div>

        <button
          type="submit"
          data-testid="login-submit"
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <>
              <div className="size-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
              <span>Signing in…</span>
            </>
          ) : (
            <span>Sign In</span>
          )}
        </button>
      </form>

      {/* Seeded credentials helper */}
      <div className="mt-6 rounded-lg border border-indigo-100 bg-indigo-50/70 p-3.5 dark:border-indigo-900/40 dark:bg-indigo-950/20">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] font-semibold text-indigo-900 dark:text-indigo-300 flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-indigo-500" />
            Seeded MVP Evaluation Account
          </span>
          <button
            type="button"
            data-testid="use-demo-creds-btn"
            onClick={handleFillDemo}
            className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 underline decoration-indigo-300 underline-offset-2"
          >
            Fill credentials
          </button>
        </div>
        <p className="text-[11px] text-zinc-600 dark:text-zinc-400">
          Email: <code className="font-mono text-zinc-800 dark:text-zinc-200">demo@krama.dev</code> · Password: <code className="font-mono text-zinc-800 dark:text-zinc-200">krama-demo-pass</code>
        </p>
      </div>

      <div className="mt-6 border-t border-zinc-100 pt-4 text-center dark:border-zinc-800">
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Need an account?{" "}
          <Link
            href="/signup"
            className="font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
          >
            Learn about access →
          </Link>
        </p>
      </div>
    </div>
  );
}

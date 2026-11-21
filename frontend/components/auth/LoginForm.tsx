"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type ApiClient, errorMessage, getApiClient, isApiError } from "@/lib/api";
import type { User } from "@krama/contracts-ts";


const IS_MOCK = process.env.NEXT_PUBLIC_API_MODE !== "http";
const DEMO_EMAIL = "demo@krama.dev";
const DEMO_PASSWORD = "krama-demo-pass";

export interface LoginFormProps {
  client?: ApiClient;
  from?: string;
  onSuccess?: (user: User) => void;
}

export function LoginForm({ client, from: propFrom, onSuccess }: LoginFormProps) {
  const t = useTranslations("auth.login");
  const router = useRouter();
  const searchParams = useSearchParams();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());

  const searchFrom = searchParams ? searchParams.get("from") : null;
  const rawFrom = propFrom ?? searchFrom;
  const redirectTarget =
    rawFrom && rawFrom.startsWith("/") && !rawFrom.startsWith("//")
      ? rawFrom
      : "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!email || !password) {
      setError(t("missingFields"));
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
        setError(t("invalid"));
      } else {
        setError(errorMessage(err, t("invalid")));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFillDemo = () => {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    setError(null);
  };

  return (
    <div className="kr-spectrum-border kr-ask rounded-[2rem] bg-ink-900/85 px-6 py-9 backdrop-blur-xl sm:px-10">
      <div className="mb-6 text-center">
        <h1 className="kr-display text-3xl font-extrabold text-white sm:text-4xl">
          {t.rich("title", { brand: (chunks) => <span className="kr-gradient-text">{chunks}</span> })}
        </h1>
        <p className="mt-2 text-sm text-ink-300">
          {t("subtitle")}
        </p>
      </div>

      {error ? (
        <div
          role="alert"
          data-testid="login-error"
          className="kr-danger kr-tone-card mb-5 flex items-start gap-2 rounded-2xl p-3 text-xs text-danger"
        >
          <svg
            className="size-4 shrink-0 mt-0.5 text-danger"
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
            className="block text-xs font-bold uppercase tracking-wider text-ink-300"
          >
            {t("email")}
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
              placeholder={DEMO_EMAIL}
              className="kr-input w-full px-4 py-3 text-sm"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-xs font-bold uppercase tracking-wider text-ink-300"
          >
            {t("password")}
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
              className="kr-input w-full px-4 py-3 text-sm"
            />
          </div>
        </div>

        <button
          type="submit"
          data-testid="login-submit"
          disabled={isLoading}
          className="kr-btn kr-btn-primary w-full px-4 py-3 text-sm"
        >
          {isLoading ? (
            <>
              <div className="size-4 rounded-full border-2 border-ink-950 border-t-transparent animate-spin" />
              <span>{t("submitting")}</span>
            </>
          ) : (
            <span>{t("submit")}</span>
          )}
        </button>
      </form>

      {/* Seeded credentials helper: mock mode only. The real password is KRAMA_DEMO_PASSWORD in .env and is never
          shown; krama-demo-pass only works with the mock client (#104). */}
      {IS_MOCK && (
      <div className="kr-plan kr-tone-card mt-6 rounded-2xl p-3.5">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] font-bold text-plan flex items-center gap-1.5">
            <span className="kr-dot !size-1.5" />
            {t("demoTitle")}
          </span>
          <button
            type="button"
            data-testid="use-demo-creds-btn"
            onClick={handleFillDemo}
            className="text-[11px] font-bold text-plan underline decoration-plan/50 underline-offset-2 hover:text-white"
          >
            {t("fillDemo")}
          </button>
        </div>
        <p className="text-[11px] text-ink-300">
          {t.rich("demoCreds", {
            email: DEMO_EMAIL,
            password: DEMO_PASSWORD,
            code: (chunks) => <code className="font-mono text-white">{chunks}</code>,
          })}
        </p>
      </div>
      )}

      <div className="mt-6 border-t border-white/10 pt-4 text-center">
        <p className="text-xs text-ink-400">
          {t("needAccount")}{" "}
          <Link
            href="/signup"
            className="font-bold text-ask hover:text-white"
          >
            {t("learnAccess")}
          </Link>
        </p>
      </div>
    </div>
  );
}

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowLeft, ArrowRight, KeyRound, LockKeyhole } from "lucide-react";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.signup");
  return { title: t("title"), description: t("description") };
}

// The seeded account's address, the env var holding its password and the recipe: the same in every language.
const DEMO_EMAIL = "demo@krama.dev";
const DEMO_PASSWORD_VAR = "KRAMA_DEMO_PASSWORD";
const SEED_RECIPE = "just seed-users";

export default async function SignupPage() {
  const t = await getTranslations("auth.signup");
  return (
    <div className="kr-spectrum-border rounded-[2rem] bg-ink-900/85 px-6 py-9 backdrop-blur-xl sm:px-10">
      <div className="mb-6 text-center">
        <div
          className="kr-float mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl text-oncolor"
          style={{ background: "var(--plan)", boxShadow: "0 0 34px -4px var(--plan)" }}
        >
          <LockKeyhole aria-hidden="true" className="size-7" />
        </div>
        <h1 className="kr-display text-3xl font-extrabold text-white">{t("title")}</h1>
        <p className="mt-3 text-sm leading-relaxed text-ink-300">
          {t("body")}
        </p>
      </div>

      <div className="kr-verify kr-tone-card space-y-3 rounded-2xl p-4">
        <div className="flex items-center gap-2">
          <span className="kr-dot" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-verify">{t("credsTitle")}</h2>
        </div>

        <p className="text-xs text-ink-300">
          {t("credsBody")}
        </p>

        <div className="space-y-1.5 rounded-xl border border-white/10 bg-ink-950/60 p-3 font-mono text-xs">
          <div className="flex justify-between gap-3">
            <span className="text-ink-400">{t("email")}</span>
            <span className="font-semibold text-white">{DEMO_EMAIL}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-ink-400">{t("password")}</span>
            <span className="font-semibold text-white">{t("passwordValue", { name: DEMO_PASSWORD_VAR })}</span>
          </div>
          <div className="flex justify-between gap-3 border-t border-white/10 pt-1.5">
            <span className="text-ink-400">{t("recipe")}</span>
            <span className="flex items-center gap-1 text-ask">
              <KeyRound aria-hidden="true" className="size-3" />
              {SEED_RECIPE}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Link href="/login" data-testid="signup-login-link" className="kr-btn kr-btn-primary w-full px-4 py-3 text-sm">
          <span>{t("signIn")}</span>
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>

        <Link href="/" className="kr-btn kr-btn-ghost w-full px-4 py-2.5 text-xs">
          <ArrowLeft aria-hidden="true" className="size-3.5" />
          {t("home")}
        </Link>
      </div>
    </div>
  );
}

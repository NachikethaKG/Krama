import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Suspense } from "react";
import { LoginForm } from "@/components/auth/LoginForm";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.login");
  return { title: t("title"), description: t("description") };
}

export default async function LoginPage() {
  const t = await getTranslations("auth.login");
  return (
    <Suspense
      fallback={
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <div className="size-8 mx-auto border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-xs text-zinc-500">{t("loading")}</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}

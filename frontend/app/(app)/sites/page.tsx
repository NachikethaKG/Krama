import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";
import { SiteSignIns } from "@/components/sites/SiteSignIns";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.sites");
  return { title: t("title"), description: t("description") };
}

/** The sites Krama is signed in to as you, and signing in to any site by hand (ADR 0012, #479). */
export default async function SitesPage({ searchParams }: { searchParams: Promise<{ url?: string }> }) {
  const { url } = await searchParams;
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
      <SiteSignIns initialUrl={typeof url === "string" ? url : ""} />
    </main>
  );
}

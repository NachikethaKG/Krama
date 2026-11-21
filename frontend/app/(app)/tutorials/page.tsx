import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { TutorialLibraryView } from "@/components/tutorials";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.tutorials");
  return { title: t("title"), description: t("description") };
}

export default function TutorialsPage() {
  return (
    <main className="py-8">
      <TutorialLibraryView />
    </main>
  );
}

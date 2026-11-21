import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";
import { ReviewQueueView } from "@/components/reviews";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shell.meta.reviews");
  return { title: t("title"), description: t("description") };
}

export default function ReviewQueuePage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
      <ReviewQueueView />
    </main>
  );
}

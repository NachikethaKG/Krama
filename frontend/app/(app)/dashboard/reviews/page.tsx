import type { Metadata } from "next";
import { ReviewQueueView } from "@/components/reviews";

export const metadata: Metadata = {
  title: "Review Queue · Krama",
  description: "Owner review queue for outdated and self-healing tutorials.",
};

export default function ReviewQueuePage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
      <ReviewQueueView />
    </main>
  );
}

import { TutorialLibraryView } from "@/components/tutorials";

export const metadata = {
  title: "My tutorials · Krama",
  description: "Your interactive tutorials, recorded from tasks Krama did and checked.",
};

export default function TutorialsPage() {
  return (
    <main className="py-8">
      <TutorialLibraryView />
    </main>
  );
}

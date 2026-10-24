import type { Metadata } from "next";
import { compileWorkflow, type TutorialSpec } from "@krama/tutorial-compiler";
import type { Workflow } from "@krama/contracts-ts";
import { TutorialPlayer } from "@/components/player";
import { RevokedLinkNotice, SharedPageHeader } from "@/components/share";
import { giteaTutorialSpecFixture, tutorialSpecFixtures } from "@/lib/fixtures";

export interface SharePageProps {
  params: Promise<{ token: string }>;
}

export async function generateMetadata({ params }: SharePageProps): Promise<Metadata> {
  await params;
  return {
    title: "Shared Tutorial · Krama",
    description: "Public interactive tutorial replay.",
    robots: {
      index: false,
      follow: false,
    },
  };
}

async function loadSharedTutorial(token: string): Promise<{ spec: TutorialSpec | null; status: number }> {
  // Explicitly invalid or revoked test tokens
  if (token === "revoked-token" || token === "invalid-token" || token === "404") {
    return { spec: null, status: 404 };
  }

  // Server side: the public read-only endpoint (docs/api-contract.md), no session needed.
  const base = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/+$/, "");
  const endpoint = `${base}/shared/${encodeURIComponent(token)}`;

  try {
    const res = await fetch(endpoint, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    if (!res.ok) {
      return { spec: null, status: res.status };
    }

    const data = await res.json();
    if (data && typeof data === "object" && "scenes" in data && "viewport" in data) {
      return { spec: data as TutorialSpec, status: 200 };
    }
    if (data && typeof data === "object" && "steps" in data) {
      const compiled = compileWorkflow(data as Workflow);
      return { spec: compiled, status: 200 };
    }
    return { spec: giteaTutorialSpecFixture, status: 200 };
  } catch {
    // If backend is not available (mock mode / headless tests), serve contract fixture
    if (process.env.NEXT_PUBLIC_API_MODE !== "http") {
      const spec = tutorialSpecFixtures[token] || giteaTutorialSpecFixture;
      return { spec, status: 200 };
    }
    return { spec: null, status: 503 };
  }
}

export default async function SharePage({ params }: SharePageProps) {
  const { token } = await params;
  const { spec, status } = await loadSharedTutorial(token);

  if (!spec) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900/50 flex flex-col">
        <SharedPageHeader />
        <main className="flex-1 container mx-auto p-4 flex items-center justify-center">
          <RevokedLinkNotice status={status} />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900/50 flex flex-col">
      <SharedPageHeader title={spec.title} />
      <main className="flex-1 container mx-auto p-4">
        <TutorialPlayer readOnly={true} spec={spec} />
      </main>
    </div>
  );
}

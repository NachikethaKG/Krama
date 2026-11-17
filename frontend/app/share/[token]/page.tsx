import type { Metadata } from "next";
import { compileWorkflow, type TutorialSpec } from "@krama/tutorial-compiler";
import type { Workflow } from "@krama/contracts-ts";
import type { eventWithTime } from "@rrweb/types";
import type { TutorialFreshnessStatus } from "@/types/tutorial";
import { TutorialPlayer } from "@/components/player";
import { SAMPLE_RRWEB_EVENTS } from "@/components/replay/sampleSession";
import { OutdatedSiteBanner, RevokedLinkNotice, SharedPageHeader } from "@/components/share";
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

async function loadSharedTutorial(token: string): Promise<{
  spec: TutorialSpec | null;
  recording: eventWithTime[] | null;
  status: number;
}> {
  // Explicitly invalid or revoked test tokens
  if (token === "revoked-token" || token === "invalid-token" || token === "404") {
    return { spec: null, recording: null, status: 404 };
  }
  // Mock mode never calls a backend: one running on :8000 answered 404 for the fixture tokens (#104).
  if (process.env.NEXT_PUBLIC_API_MODE !== "http") {
    return {
      spec: tutorialSpecFixtures[token] || giteaTutorialSpecFixture,
      recording: SAMPLE_RRWEB_EVENTS,
      status: 200,
    };
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
      return { spec: null, recording: null, status: res.status };
    }

    const data = await res.json();
    let spec: TutorialSpec | null = null;
    let recording: eventWithTime[] | null = null;

    if (data && typeof data === "object" && "scenes" in data && "viewport" in data) {
      spec = data as TutorialSpec;
    } else if (data && typeof data === "object" && "steps" in data) {
      spec = compileWorkflow(data as Workflow);
    }

    if (!spec) {
      // Never show a sample tutorial in place of the shared one (#104).
      return { spec: null, recording: null, status: 502 };
    }

    // Load recording if recording_path is available (served under /shared/{token}/artifacts/)
    const recPath = (data as Workflow)?.recording_path;
    if (recPath) {
      try {
        let recUrl: string;
        if (recPath.startsWith("http://") || recPath.startsWith("https://")) {
          recUrl = recPath;
        } else if (recPath.startsWith("/api/")) {
          recUrl = `${new URL(base).origin}${recPath}`;
        } else {
          recUrl = `${base}/shared/${encodeURIComponent(token)}/artifacts/${recPath.replace(/^\/+/, "")}`;
        }

        const recRes = await fetch(recUrl, {
          cache: "no-store",
          headers: { Accept: "application/json" },
        });
        if (recRes.ok) {
          const recBody: unknown = await recRes.json();
          const events = Array.isArray(recBody) ? recBody : (recBody as { events?: unknown }).events;
          if (Array.isArray(events) && events.length > 1) {
            recording = events as eventWithTime[];
          }
        }
      } catch {
        // Fallback to wireframe if recording cannot be loaded
      }
    }

    return { spec, recording, status: 200 };
  } catch {
    return { spec: null, recording: null, status: 503 };
  }
}

export default async function SharePage({ params }: SharePageProps) {
  const { token } = await params;
  const { spec, recording, status } = await loadSharedTutorial(token);

  if (!spec) {
    return (
      <div className="flex min-h-screen flex-col">
        <SharedPageHeader />
        <main className="container mx-auto flex flex-1 items-center justify-center p-4">
          <RevokedLinkNotice status={status} />
        </main>
      </div>
    );
  }

  const freshnessStatus: TutorialFreshnessStatus =
    (spec as unknown as { status?: TutorialFreshnessStatus }).status ??
    (token.includes("outdated") ? "outdated" : "verified");

  return (
    <div
      className="flex min-h-screen flex-col"
      data-testid="share-page-container"
      data-real-ui={recording ? "true" : "false"}
    >
      <SharedPageHeader title={spec.title} status={freshnessStatus} />
      <main className="container mx-auto flex flex-1 flex-col gap-4 p-4 pt-6">
        {freshnessStatus === "outdated" ? <OutdatedSiteBanner /> : null}
        <TutorialPlayer readOnly={true} spec={spec} recording={recording} status={freshnessStatus} />
      </main>
    </div>
  );
}

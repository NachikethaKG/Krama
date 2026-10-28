import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";
import type { eventWithTime } from "@rrweb/types";
import { SETTLED_FRAME_STYLE, TutorialStage, WorkflowTutorial } from "@/components/player";
import { MockApiClient } from "@/lib/api";
import { giteaTutorialSpecFixture } from "@/lib/fixtures";

// rrweb needs a real browser; here the stage only has to mount the real-page component instead of the wireframe.
vi.mock("rrweb", () => ({ Replayer: vi.fn() }));

const RECORDING = [
  { type: 4, timestamp: 1_000, data: { href: "http://localhost:3001/", width: 1280, height: 800 } },
  { type: 2, timestamp: 1_010, data: {} },
] as unknown as eventWithTime[];

function scene(overrides: Partial<Scene>): Scene {
  const first = giteaTutorialSpecFixture.scenes[0];
  return {
    ...first,
    highlight: { bbox: [500, 1200, 150, 40], style: "solid_box", padding: 8, color: "#4f46e5" },
    scroll: { x: 0, y: 900 },
    recording: { start_ms: 4_000, end_ms: 5_000, baseline_snapshot_index: null },
    ...overrides,
  };
}

function stage(currentScene: Scene, recording: eventWithTime[] | null, currentTimeMs = 0) {
  const spec: TutorialSpec = { ...giteaTutorialSpecFixture, viewport: { width: 1280, height: 800 } };
  return render(
    <TutorialStage
      spec={spec}
      currentScene={currentScene}
      currentTimeMs={currentTimeMs}
      isZoomEnabled={false}
      isCaptionsEnabled
      recording={recording}
    />,
  );
}

describe("tutorial on the real UI (#83)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the recorded page and places the highlight at bbox minus the step's scroll", () => {
    stage(scene({}), RECORDING);

    expect(screen.getByTestId("recorded-page")).toBeInTheDocument();
    const box = screen.getByTestId("target-highlight");
    // Page y 1200 with the window scrolled to 900 is 300 px down the screen (minus the 8 px padding).
    expect(box.style.top).toBe("292px");
    expect(box.style.left).toBe("492px");
  });

  it("drops the highlight once a click's result is shown, where the clicked element may be gone", () => {
    const click = scene({ action: { type: "click", value: null } });
    const clickMs = click.cursor?.click_ms;
    expect(clickMs).toEqual(expect.any(Number));

    const before = stage(click, RECORDING, 0);
    expect(screen.getByTestId("target-highlight")).toBeInTheDocument();
    before.unmount();

    stage(click, RECORDING, (clickMs as number) + 50);
    expect(screen.queryByTestId("target-highlight")).not.toBeInTheDocument();
  });

  it("keeps the highlight on a field after typing into it", () => {
    const fill = scene({ action: { type: "fill", value: "demo" } });
    stage(fill, RECORDING, (fill.cursor?.click_ms ?? 0) + 50);
    expect(screen.getByTestId("target-highlight")).toBeInTheDocument();
  });

  it("shows each frame settled, so elements that fade in (Gitea's dialogs) aren't frozen invisible", async () => {
    const { Replayer } = await import("rrweb");
    stage(scene({}), RECORDING);

    await waitFor(() => expect(Replayer).toHaveBeenCalled());
    const config = vi.mocked(Replayer).mock.calls[0][1] as { insertStyleRules?: string[] };
    expect(config.insertStyleRules).toContain(SETTLED_FRAME_STYLE);
    expect(SETTLED_FRAME_STYLE).toMatch(/html\.rrweb-paused \*[^{]*\{[^}]*animation: none !important/);
  });

  it("keeps the wireframe and page coordinates without a recording", () => {
    stage(scene({}), null);

    expect(screen.queryByTestId("recorded-page")).not.toBeInTheDocument();
    expect(screen.getByTestId("target-highlight").style.top).toBe("1192px");
  });

  it("loads a stored workflow by id and says whether it can play the real UI", async () => {
    // Mock mode's fixture workflow has no step timing, so it must not pretend to replay its recording.
    vi.spyOn(MockApiClient.prototype, "getWorkflow");
    const id = Object.keys((await import("@/lib/fixtures")).workflowFixtures)[0];

    render(<WorkflowTutorial workflowId={id} />);

    const root = await screen.findByTestId("workflow-tutorial");
    expect(root.dataset.realUi).toBe("false");
    expect(screen.getByTestId("tutorial-player-root")).toBeInTheDocument();
  });

  it("says plainly when the workflow doesn't exist", async () => {
    render(<WorkflowTutorial workflowId="6f1c2a4e-0000-4b8a-9a1b-000000000000" />);

    await waitFor(() =>
      expect(screen.getByTestId("workflow-tutorial-error")).toHaveTextContent("no stored workflow"),
    );
  });

  it("lists only verified workflows as tutorials in mock mode", async () => {
    const page = await new MockApiClient().getWorkflows();

    expect(page.items.length).toBeGreaterThan(0);
    expect(page.items.every((w) => w.status === "verified" && w.step_count > 0)).toBe(true);
  });
});

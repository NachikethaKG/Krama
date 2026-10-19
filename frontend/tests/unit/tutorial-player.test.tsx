import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TutorialSpec } from "@krama/tutorial-compiler";
import { TutorialPlayer } from "@/components/player";
import { giteaTutorialSpecFixture } from "@/lib/fixtures";

describe("TutorialPlayer & Player Components", () => {
  beforeEach(() => {
    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockImplementation(() => Promise.resolve()),
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the tutorial player with title, controls, stage, and step list", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    // Header title
    expect(screen.getAllByText("Create a repository in local Gitea").length).toBeGreaterThan(0);

    // Controls
    expect(screen.getByTestId("tutorial-controls")).toBeInTheDocument();
    expect(screen.getByTestId("control-play-pause")).toBeInTheDocument();
    expect(screen.getByTestId("control-prev-step")).toBeInTheDocument();
    expect(screen.getByTestId("control-next-step")).toBeInTheDocument();

    // Stage
    expect(screen.getByTestId("tutorial-stage-container")).toBeInTheDocument();
    expect(screen.getByTestId("camera-viewport")).toBeInTheDocument();

    // Step list
    expect(screen.getByTestId("step-list")).toBeInTheDocument();
    expect(screen.getByTestId("step-item-1")).toBeInTheDocument();

    // First step instruction
    expect(screen.getByTestId("instruction-text")).toHaveTextContent(
      "Open the + menu at the top right.",
    );
  });

  it("handles Play / Pause toggle state transitions", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const playPauseBtn = screen.getByTestId("control-play-pause");
    expect(playPauseBtn).toHaveAttribute("aria-label", "Play tutorial");

    // Click to Play
    fireEvent.click(playPauseBtn);
    expect(playPauseBtn).toHaveAttribute("aria-label", "Pause tutorial");

    // Click to Pause
    fireEvent.click(playPauseBtn);
    expect(playPauseBtn).toHaveAttribute("aria-label", "Play tutorial");
  });

  it("advances to next step and returns to previous step", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const nextBtn = screen.getByTestId("control-next-step");
    const prevBtn = screen.getByTestId("control-prev-step");

    // Initially at Step 1
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();

    // Advance to Step 2
    fireEvent.click(nextBtn);
    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();
    expect(screen.getByTestId("instruction-text")).toHaveTextContent(
      "Click New Repository in the menu.",
    );

    // Advance to Step 3
    fireEvent.click(nextBtn);
    expect(screen.getByText("Step 3 of 5")).toBeInTheDocument();
    expect(screen.getByTestId("instruction-text")).toHaveTextContent(
      "Enter demo-repo as the repository name.",
    );

    // Return to Step 2
    fireEvent.click(prevBtn);
    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();
  });

  it("resets step progress when Replay Step is clicked", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const replayBtn = screen.getByTestId("control-replay-step");
    expect(replayBtn).toBeInTheDocument();

    // Clicking replay should not crash and keep current step
    fireEvent.click(replayBtn);
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
  });

  it("switches camera transform between auto-zoom and overview with Zoom Toggle", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const zoomBtn = screen.getByTestId("control-toggle-zoom");
    const cameraViewport = screen.getByTestId("camera-viewport");

    // Default: Zoom is enabled (spec camera scale = 1.35)
    expect(zoomBtn).toHaveAttribute("aria-pressed", "true");
    expect(cameraViewport.style.transform).toContain("scale(1.35)");

    // Toggle Zoom Off -> Overview (1.0x)
    fireEvent.click(zoomBtn);
    expect(zoomBtn).toHaveAttribute("aria-pressed", "false");
    expect(cameraViewport.style.transform).toBe("none");

    // Toggle Zoom On -> Auto-zoom
    fireEvent.click(zoomBtn);
    expect(zoomBtn).toHaveAttribute("aria-pressed", "true");
    expect(cameraViewport.style.transform).toContain("scale(1.35)");
  });

  it("toggles caption overlay visibility with Captions Toggle", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const captionsBtn = screen.getByTestId("control-toggle-captions");

    // Captions initially visible
    expect(screen.getByTestId("tutorial-caption")).toBeInTheDocument();
    expect(captionsBtn).toHaveAttribute("aria-pressed", "true");

    // Toggle Captions Off
    fireEvent.click(captionsBtn);
    expect(screen.queryByTestId("tutorial-caption")).not.toBeInTheDocument();
    expect(captionsBtn).toHaveAttribute("aria-pressed", "false");

    // Toggle Captions On
    fireEvent.click(captionsBtn);
    expect(screen.getByTestId("tutorial-caption")).toBeInTheDocument();
  });

  it("seeks directly to clicked step from the step list sidebar", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    // Click step 4 in sidebar
    const step4Btn = screen.getByTestId("step-item-4");
    fireEvent.click(step4Btn);

    expect(screen.getByText("Step 4 of 5")).toBeInTheDocument();
    expect(screen.getByTestId("instruction-text")).toHaveTextContent(
      "Check Initialize Repository to add .gitignore, License and README.",
    );
  });

  it("copies instruction text and input value to clipboard with Copy button", async () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    // Step 1 copy button
    const copyButtons = screen.getAllByTestId("copy-button");
    expect(copyButtons.length).toBeGreaterThan(0);

    const firstCopyBtn = copyButtons[0];
    fireEvent.click(firstCopyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "Open the + menu at the top right.",
    );

    // Visual copied indicator appears
    expect(await screen.findByText("Copied!")).toBeInTheDocument();
  });

  it("supports keyboard navigation shortcuts (Space, ArrowRight, ArrowLeft, R, Z, C)", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const playPauseBtn = screen.getByTestId("control-play-pause");
    const zoomBtn = screen.getByTestId("control-toggle-zoom");
    const captionsBtn = screen.getByTestId("control-toggle-captions");

    // Space: Play
    fireEvent.keyDown(window, { key: " " });
    expect(playPauseBtn).toHaveAttribute("aria-label", "Pause tutorial");

    // ArrowRight: Next Step
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();

    // ArrowLeft: Prev Step
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();

    // Z: Toggle Zoom
    fireEvent.keyDown(window, { key: "z" });
    expect(zoomBtn).toHaveAttribute("aria-pressed", "false");

    // C: Toggle Captions
    fireEvent.keyDown(window, { key: "c" });
    expect(captionsBtn).toHaveAttribute("aria-pressed", "false");

    // R: Replay step
    fireEvent.keyDown(window, { key: "r" });
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
  });

  describe("Edge Cases", () => {
    it("handles single-step tutorial gracefully", () => {
      const singleStepSpec: TutorialSpec = {
        ...giteaTutorialSpecFixture,
        scenes: [giteaTutorialSpecFixture.scenes[0]],
        total_duration_ms: giteaTutorialSpecFixture.scenes[0].duration_ms,
      };

      render(<TutorialPlayer spec={singleStepSpec} />);

      expect(screen.getByText("Step 1 of 1")).toBeInTheDocument();
      const nextBtn = screen.getByTestId("control-next-step");
      expect(nextBtn).toBeDisabled();

      // Clicking next does not crash or advance
      fireEvent.click(nextBtn);
      expect(screen.getByText("Step 1 of 1")).toBeInTheDocument();
    });

    it("handles rapid clicking of next and previous buttons without exceeding bounds", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

      const nextBtn = screen.getByTestId("control-next-step");
      const prevBtn = screen.getByTestId("control-prev-step");

      // Click next 10 times rapidly
      for (let i = 0; i < 10; i++) {
        fireEvent.click(nextBtn);
      }
      expect(screen.getByText("Step 5 of 5")).toBeInTheDocument();

      // Click prev 10 times rapidly
      for (let i = 0; i < 10; i++) {
        fireEvent.click(prevBtn);
      }
      expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
    });

    it("handles steps with no zoom or cursor data (e.g. navigate / wait)", () => {
      const noCursorSpec: TutorialSpec = {
        ...giteaTutorialSpecFixture,
        scenes: [
          {
            id: "scene-nav",
            step_seq: 1,
            title: "Navigate",
            start_ms: 0,
            duration_ms: 2000,
            action: { type: "navigate", value: "https://git.local/login" },
            sensitive: false,
            caption: { text: "Navigate to the login screen.", words: null },
            recording: { start_ms: 0, end_ms: 2000, baseline_snapshot_index: 0 },
            scroll: null,
            camera: null,
            cursor: null,
            highlight: null,
          },
        ],
      };

      render(<TutorialPlayer spec={noCursorSpec} />);

      expect(screen.getByTestId("instruction-text")).toHaveTextContent(
        "Navigate to the login screen.",
      );
      expect(screen.queryByTestId("tutorial-cursor")).not.toBeInTheDocument();
      expect(screen.queryByTestId("target-highlight")).not.toBeInTheDocument();

      const cameraViewport = screen.getByTestId("camera-viewport");
      expect(cameraViewport.style.transform).toBe("none");
    });
  });
});

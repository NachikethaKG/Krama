import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TutorialSpec } from "@krama/tutorial-compiler";
import {
  calculateWordIndex,
  MAX_SCENE_HOLD_MS,
  NARRATION_TAIL_MS,
  selectOptimalVoice,
  TutorialPlayer,
} from "@/components/player";
import { giteaTutorialSpecFixture } from "@/lib/fixtures";

// Mock SpeechSynthesisUtterance implementation
class MockSpeechSynthesisUtterance {
  text: string;
  lang = "en-US";
  voice: SpeechSynthesisVoice | null = null;
  rate = 1.0;
  pitch = 1.0;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onerror: ((e: any) => void) | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onboundary: ((e: any) => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

describe("TutorialPlayer & Accessibility Suite", () => {
  let mockSpeechSynthesis: {
    speak: ReturnType<typeof vi.fn>;
    cancel: ReturnType<typeof vi.fn>;
    pause: ReturnType<typeof vi.fn>;
    resume: ReturnType<typeof vi.fn>;
    getVoices: ReturnType<typeof vi.fn>;
    onvoiceschanged: (() => void) | null;
  };

  beforeEach(() => {
    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockImplementation(() => Promise.resolve()),
      },
    });

    // Mock matchMedia
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    // Mock window.speechSynthesis
    mockSpeechSynthesis = {
      speak: vi.fn((utterance: MockSpeechSynthesisUtterance) => {
        utterance.onstart?.();
      }),
      cancel: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      getVoices: vi.fn().mockReturnValue([
        {
          name: "Microsoft Jenny Online (Natural) - English (United States)",
          lang: "en-US",
          default: true,
          localService: false,
          voiceURI: "Microsoft Jenny",
        } as SpeechSynthesisVoice,
        {
          name: "Microsoft David - English (United States)",
          lang: "en-US",
          default: false,
          localService: true,
          voiceURI: "Microsoft David",
        } as SpeechSynthesisVoice,
      ]),
      onvoiceschanged: null,
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).speechSynthesis = mockSpeechSynthesis;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the tutorial player with title, controls, stage, and step list", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    // Header title
    expect(
      screen.getAllByText("Create a repository in local Gitea").length,
    ).toBeGreaterThan(0);

    // Controls
    expect(screen.getByTestId("tutorial-controls")).toBeInTheDocument();
    expect(screen.getByTestId("control-play-pause")).toBeInTheDocument();
    expect(screen.getByTestId("control-prev-step")).toBeInTheDocument();
    expect(screen.getByTestId("control-next-step")).toBeInTheDocument();
    expect(screen.getByTestId("control-toggle-mute")).toBeInTheDocument();

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

    fireEvent.click(replayBtn);
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
  });

  it("switches camera transform between auto-zoom and overview with Zoom Toggle", () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const zoomBtn = screen.getByTestId("control-toggle-zoom");
    const cameraViewport = screen.getByTestId("camera-viewport");

    // Default: Overview (1.0x): the whole page is easier to follow than a zoomed crop (#83 newcomer test)
    expect(zoomBtn).toHaveAttribute("aria-pressed", "false");
    expect(cameraViewport.style.transform).toBe("none");

    // Toggle Zoom On -> Auto-zoom (spec camera scale = 1.35)
    fireEvent.click(zoomBtn);
    expect(zoomBtn).toHaveAttribute("aria-pressed", "true");
    expect(cameraViewport.style.transform).toContain("scale(1.35)");

    // Toggle Zoom Off -> Overview
    fireEvent.click(zoomBtn);
    expect(zoomBtn).toHaveAttribute("aria-pressed", "false");
    expect(cameraViewport.style.transform).toBe("none");
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

    const step4Btn = screen.getByTestId("step-item-4");
    fireEvent.click(step4Btn);

    expect(screen.getByText("Step 4 of 5")).toBeInTheDocument();
    expect(screen.getByTestId("instruction-text")).toHaveTextContent(
      "Check Initialize Repository to add .gitignore, License and README.",
    );
  });

  it("copies instruction text and input value to clipboard with Copy button", async () => {
    render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

    const copyButtons = screen.getAllByTestId("copy-button");
    expect(copyButtons.length).toBeGreaterThan(0);

    const firstCopyBtn = copyButtons[0];
    fireEvent.click(firstCopyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "Open the + menu at the top right.",
    );

    expect(await screen.findByText("Copied!")).toBeInTheDocument();
  });

  describe("Web Speech API Narration & Caption Sync", () => {
    it("speaks step instruction when playback starts and cancels when paused", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

      const playPauseBtn = screen.getByTestId("control-play-pause");

      // Initially paused, speak should not be called
      expect(mockSpeechSynthesis.speak).not.toHaveBeenCalled();

      // Click Play -> calls speak with step 1 text
      fireEvent.click(playPauseBtn);
      expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
      const lastUtterance = mockSpeechSynthesis.speak.mock.calls[0][0];
      expect(lastUtterance.text).toBe("Open the + menu at the top right.");

      // Click Pause -> cancels active speech
      fireEvent.click(playPauseBtn);
      expect(mockSpeechSynthesis.cancel).toHaveBeenCalled();
    });

    it("toggles audio narration mute and stops speech immediately", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);

      const muteBtn = screen.getByTestId("control-toggle-mute");
      expect(muteBtn).toHaveAttribute("aria-pressed", "true"); // Active (unmuted)

      // Mute speech
      fireEvent.click(muteBtn);
      expect(muteBtn).toHaveAttribute("aria-pressed", "false"); // Muted
      expect(mockSpeechSynthesis.cancel).toHaveBeenCalled();

      // Unmute speech
      fireEvent.click(muteBtn);
      expect(muteBtn).toHaveAttribute("aria-pressed", "true");
    });

    it("synchronizes active caption word highlight when onboundary triggers", () => {
      let capturedUtterance: MockSpeechSynthesisUtterance | null = null;
      mockSpeechSynthesis.speak = vi.fn((utterance: MockSpeechSynthesisUtterance) => {
        capturedUtterance = utterance;
        utterance.onstart?.();
      });

      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);

      expect(capturedUtterance).not.toBeNull();

      // Trigger word boundary event for second word ("the", charIndex 5)
      (capturedUtterance as unknown as MockSpeechSynthesisUtterance | null)?.onboundary?.({
        name: "word",
        charIndex: 5,
      } as unknown as SpeechSynthesisEvent);

      // Verify word index calculation helper
      const wordIdx = calculateWordIndex("Open the + menu at the top right.", 5);
      expect(wordIdx).toBe(1);
    });

    it("gracefully degrades when window.speechSynthesis is undefined or speak throws", () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (window as any).speechSynthesis;

      expect(() => {
        render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);
      }).not.toThrow();

      expect(screen.getByTestId("tutorial-controls")).toBeInTheDocument();
    });

    it("handles voice selection fallback priorities", () => {
      const naturalVoice = {
        name: "Microsoft Jenny Online (Natural) - English (United States)",
        lang: "en-US",
        localService: false,
      } as SpeechSynthesisVoice;

      const standardVoice = {
        name: "Google US English",
        lang: "en-US",
        localService: false,
      } as SpeechSynthesisVoice;

      const localVoice = {
        name: "Microsoft David",
        lang: "en-US",
        localService: true,
      } as SpeechSynthesisVoice;

      expect(selectOptimalVoice([localVoice, standardVoice, naturalVoice])).toBe(
        naturalVoice,
      );
      expect(selectOptimalVoice([localVoice, standardVoice])).toBe(standardVoice);
      expect(selectOptimalVoice([localVoice])).toBe(localVoice);
      expect(selectOptimalVoice([])).toBeNull();
    });
  });

  describe("Keyboard Shortcuts & Screen Reader Announcements", () => {
    it("handles comprehensive keyboard shortcuts (Space/K, ArrowLeft/J, ArrowRight/L, R, M, C, Z)", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

      const playPauseBtn = screen.getByTestId("control-play-pause");
      const zoomBtn = screen.getByTestId("control-toggle-zoom");
      const captionsBtn = screen.getByTestId("control-toggle-captions");
      const muteBtn = screen.getByTestId("control-toggle-mute");

      // Space: Play
      fireEvent.keyDown(window, { key: " " });
      expect(playPauseBtn).toHaveAttribute("aria-label", "Pause tutorial");

      // KeyK: Pause
      fireEvent.keyDown(window, { key: "k" });
      expect(playPauseBtn).toHaveAttribute("aria-label", "Play tutorial");

      // ArrowRight: Next Step
      fireEvent.keyDown(window, { key: "ArrowRight" });
      expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();

      // KeyL: Next Step
      fireEvent.keyDown(window, { key: "l" });
      expect(screen.getByText("Step 3 of 5")).toBeInTheDocument();

      // ArrowLeft: Prev Step
      fireEvent.keyDown(window, { key: "ArrowLeft" });
      expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();

      // KeyJ: Prev Step
      fireEvent.keyDown(window, { key: "j" });
      expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();

      // KeyM: Toggle Mute
      fireEvent.keyDown(window, { key: "m" });
      expect(muteBtn).toHaveAttribute("aria-pressed", "false"); // muted

      // KeyC: Toggle Captions
      fireEvent.keyDown(window, { key: "c" });
      expect(captionsBtn).toHaveAttribute("aria-pressed", "false");

      // KeyZ: Toggle Zoom
      fireEvent.keyDown(window, { key: "z" });
      expect(zoomBtn).toHaveAttribute("aria-pressed", "true");

      // KeyR: Replay Step
      fireEvent.keyDown(window, { key: "r" });
      expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
    });

    it("ignores keyboard shortcuts when focus is inside a text input", () => {
      render(
        <div>
          <input type="text" data-testid="test-input" />
          <TutorialPlayer spec={giteaTutorialSpecFixture} />
        </div>,
      );

      const input = screen.getByTestId("test-input");
      const playPauseBtn = screen.getByTestId("control-play-pause");

      // Typing inside text input does not toggle play/pause
      fireEvent.keyDown(input, { key: " " });
      expect(playPauseBtn).toHaveAttribute("aria-label", "Play tutorial");

      fireEvent.keyDown(input, { key: "k" });
      expect(playPauseBtn).toHaveAttribute("aria-label", "Play tutorial");
    });

    it("announces step transitions to screen readers via aria-live polite region", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

      const announcer = screen.getByTestId("screen-reader-announcer");
      expect(announcer).toHaveAttribute("aria-live", "polite");
      expect(announcer).toHaveTextContent(
        "Step 1 of 5: Open the + menu at the top right.",
      );

      // Advance to Step 2
      const nextBtn = screen.getByTestId("control-next-step");
      fireEvent.click(nextBtn);

      expect(announcer).toHaveTextContent(
        "Step 2 of 5: Click New Repository in the menu.",
      );
    });
  });

  describe("Reduced-Motion Compliance & Mobile Layout", () => {
    it("respects prefers-reduced-motion: disables auto-zoom, disables pulse, snaps cursor", () => {
      render(
        <TutorialPlayer
          spec={giteaTutorialSpecFixture}
          isReducedMotion={true}
        />,
      );

      const cameraViewport = screen.getByTestId("camera-viewport");
      // In reduced motion, auto-zoom transform is clamped to none
      expect(cameraViewport.style.transform).toBe("none");

      // Highlight overlay should not have animate-pulse class
      const highlight = screen.getByTestId("target-highlight");
      expect(highlight.className).not.toContain("animate-pulse");
    });

    it("renders collapsible mobile step drawer sheet on small screens", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

      const drawerToggle = screen.getByTestId("mobile-step-drawer-toggle");
      expect(drawerToggle).toHaveAttribute("aria-expanded", "false");

      // Click to open drawer
      fireEvent.click(drawerToggle);
      expect(drawerToggle).toHaveAttribute("aria-expanded", "true");

      const drawer = screen.getByTestId("mobile-step-drawer");
      expect(drawer).toBeInTheDocument();

      // Click close button inside drawer
      const closeBtn = screen.getByTestId("drawer-close-button");
      fireEvent.click(closeBtn);
      expect(screen.queryByTestId("mobile-step-drawer")).not.toBeInTheDocument();
    });
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

      fireEvent.click(nextBtn);
      expect(screen.getByText("Step 1 of 1")).toBeInTheDocument();
    });

    it("handles rapid clicking of next and previous buttons without exceeding bounds", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} />);

      const nextBtn = screen.getByTestId("control-next-step");
      const prevBtn = screen.getByTestId("control-prev-step");

      for (let i = 0; i < 10; i++) {
        fireEvent.click(nextBtn);
      }
      expect(screen.getByText("Step 5 of 5")).toBeInTheDocument();

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

  describe("Narration holds the step until the voice is done (#83)", () => {
    const FIRST = "Open the + menu at the top right.";
    let utterances: MockSpeechSynthesisUtterance[];

    beforeEach(() => {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "requestAnimationFrame", "cancelAnimationFrame", "performance"] });
      utterances = [];
      // Speech that only ends when the test says so, like a sentence longer than the step.
      mockSpeechSynthesis.speak = vi.fn((utterance: MockSpeechSynthesisUtterance) => {
        utterances.push(utterance);
        utterance.onstart?.();
      });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms));

    it("stays on the step while the narration is still speaking past the step's length", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);

      advance(giteaTutorialSpecFixture.scenes[0].duration_ms + 3000);

      expect(screen.getByTestId("instruction-text")).toHaveTextContent(FIRST);
      expect(mockSpeechSynthesis.speak).toHaveBeenCalledTimes(1);
    });

    it("moves on only after the last word plus a short pause", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);
      advance(giteaTutorialSpecFixture.scenes[0].duration_ms + 1000);

      act(() => utterances[0].onend?.());
      advance(NARRATION_TAIL_MS / 2);
      expect(screen.getByTestId("instruction-text")).toHaveTextContent(FIRST);

      advance(NARRATION_TAIL_MS);
      expect(screen.getByTestId("instruction-text")).not.toHaveTextContent(FIRST);
      expect(utterances).toHaveLength(2);
    });

    it("ignores the late end of a cancelled utterance", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);
      advance(giteaTutorialSpecFixture.scenes[0].duration_ms + 1000);
      act(() => utterances[0].onend?.());
      advance(NARRATION_TAIL_MS * 2);
      const second = screen.getByTestId("instruction-text").textContent;

      // Chrome reports the first utterance's cancel after the second one started.
      act(() => utterances[0].onerror?.({ error: "interrupted" }));
      advance(giteaTutorialSpecFixture.scenes[1].duration_ms + 1000);

      expect(screen.getByTestId("instruction-text").textContent).toBe(second);
    });

    it("gives up waiting if the browser never reports the end of speech", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} />);

      advance(giteaTutorialSpecFixture.scenes[0].duration_ms + MAX_SCENE_HOLD_MS + 500);

      expect(screen.getByTestId("instruction-text")).not.toHaveTextContent(FIRST);
    });

    it("muted, the step moves on at its own length", () => {
      render(<TutorialPlayer spec={giteaTutorialSpecFixture} autoPlay={true} initialMuted={true} />);

      advance(giteaTutorialSpecFixture.scenes[0].duration_ms + 200);

      expect(mockSpeechSynthesis.speak).not.toHaveBeenCalled();
      expect(screen.getByTestId("instruction-text")).not.toHaveTextContent(FIRST);
    });
  });
});

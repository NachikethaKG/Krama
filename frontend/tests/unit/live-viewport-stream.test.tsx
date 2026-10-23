import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LiveViewportStream } from "@/components/runs/LiveViewportStream";
import type { LiveScreenshotFrame } from "@/hooks/useRunStream";

describe("LiveViewportStream Component", () => {
  it("renders skeleton loader when frame is null", () => {
    render(<LiveViewportStream frame={null} targetUrl="https://github.com/login" />);

    expect(screen.getByTestId("live-viewport-stream")).toBeInTheDocument();
    expect(screen.getByTestId("viewport-skeleton")).toBeInTheDocument();
    expect(screen.getByText(/Waiting for browser viewport frame/i)).toBeInTheDocument();
    expect(screen.queryByTestId("live-stream-image")).not.toBeInTheDocument();
  });

  it("renders skeleton loader when isLoading is true even if frame exists", () => {
    const frame: LiveScreenshotFrame = {
      imageUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      stepSeq: 1,
      timestampMs: 1700000000000,
    };

    render(
      <LiveViewportStream
        frame={frame}
        isLoading={true}
        targetUrl="https://github.com/login"
      />,
    );

    expect(screen.getByTestId("viewport-skeleton")).toBeInTheDocument();
    expect(screen.queryByTestId("live-stream-image")).not.toBeInTheDocument();
  });

  it("renders live indicator badge, dot, and target URL", () => {
    render(
      <LiveViewportStream
        frame={null}
        targetUrl="https://github.com/krama-org/repo/issues/new"
      />,
    );

    expect(screen.getByTestId("live-indicator-badge")).toHaveTextContent("LIVE HEADLESS");
    expect(screen.getByTestId("live-dot")).toBeInTheDocument();
    expect(screen.getByTestId("stream-target-url")).toHaveTextContent(
      "https://github.com/krama-org/repo/issues/new",
    );
  });

  it("renders image and updates timestamp when frame arrives", () => {
    const frame: LiveScreenshotFrame = {
      imageUrl: "https://example.com/screenshot1.png",
      stepSeq: 2,
      timestampMs: 1700000000000,
    };

    const { rerender } = render(
      <LiveViewportStream
        frame={frame}
        targetUrl="https://github.com/krama-org"
      />,
    );

    expect(screen.queryByTestId("viewport-skeleton")).not.toBeInTheDocument();
    const image = screen.getByTestId("live-stream-image") as HTMLImageElement;
    expect(image).toBeInTheDocument();
    expect(image.src).toBe("https://example.com/screenshot1.png");
    expect(screen.getByTestId("stream-timestamp")).toBeInTheDocument();

    // Rerender with next frame
    const nextFrame: LiveScreenshotFrame = {
      imageUrl: "https://example.com/screenshot2.png",
      stepSeq: 3,
      timestampMs: 1700000005000,
    };

    rerender(
      <LiveViewportStream
        frame={nextFrame}
        targetUrl="https://github.com/krama-org"
      />,
    );

    const updatedImage = screen.getByTestId("live-stream-image") as HTMLImageElement;
    expect(updatedImage.src).toBe("https://example.com/screenshot2.png");
  });
});

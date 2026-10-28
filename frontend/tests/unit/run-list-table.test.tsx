import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunListTable, formatDateTime, formatDuration } from "@/components/runs/RunListTable";
import { mockRunsList } from "@/lib/fixtures";

describe("RunListTable", () => {
  it("renders loading state when isLoading is true", () => {
    render(<RunListTable runs={[]} isLoading={true} />);
    expect(screen.getByTestId("runs-loading")).toBeInTheDocument();
    expect(screen.getByText("Loading runs…")).toBeInTheDocument();
  });

  it("renders error alert when error is provided", () => {
    render(<RunListTable runs={[]} error="Failed to fetch backend runs: 500" />);
    expect(screen.getByTestId("runs-error")).toBeInTheDocument();
    expect(screen.getByText("Failed to fetch backend runs: 500")).toBeInTheDocument();
  });

  it("renders empty state when runs list is empty", () => {
    render(<RunListTable runs={[]} />);
    expect(screen.getByTestId("runs-empty-state")).toBeInTheDocument();
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
  });

  it("renders table with rows for provided runs", () => {
    const sampleRuns = mockRunsList.slice(0, 3);
    render(<RunListTable runs={sampleRuns} />);

    expect(screen.getByTestId("runs-list-table")).toBeInTheDocument();
    for (const run of sampleRuns) {
      expect(screen.getByTestId(`run-row-${run.id}`)).toBeInTheDocument();
      expect(screen.getByText(run.id)).toBeInTheDocument();
    }
  });

  it("renders retry count indicator when run has retries", () => {
    const runWithRetries = [mockRunsList[10]]; // run-11 has retryCount: 2
    render(<RunListTable runs={runWithRetries} />);

    expect(screen.getByTestId("run-retries")).toHaveTextContent("Retried 2 times");
  });

  describe("formatDateTime & formatDuration helpers", () => {
    it("formats durations accurately", () => {
      expect(formatDuration(null)).toBe("—");
      expect(formatDuration(undefined)).toBe("—");
      expect(formatDuration(5)).toBe("5s");
      expect(formatDuration(65)).toBe("1m 5s");
      expect(formatDuration(120)).toBe("2m 0s");
    });

    it("formats valid and invalid dates safely", () => {
      expect(formatDateTime(null)).toBe("—");
      expect(formatDateTime("2026-10-06T12:00:00Z")).toContain("2026");
      expect(formatDateTime("invalid-date")).toBe("invalid-date");
    });
  });
});

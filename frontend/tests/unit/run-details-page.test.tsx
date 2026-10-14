import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { RunDetailHeader } from "@/components/runs/RunDetailHeader";
import { RunDetailView } from "@/components/runs/RunDetailView";
import { mockRunDetails } from "@/lib/fixtures";
import * as apiModule from "@/lib/api";

describe("RunDetailHeader", () => {
  const details = mockRunDetails["run-1"];

  it("renders run metadata and summary KPI counts", () => {
    render(<RunDetailHeader runDetails={details} />);

    expect(screen.getByTestId("back-to-runs-link")).toBeInTheDocument();
    expect(screen.getByTestId("run-detail-id")).toHaveTextContent("run-1");
    expect(screen.getByTestId("run-detail-prompt")).toHaveTextContent(details.run.prompt);
    expect(screen.getByTestId("stat-total-steps")).toHaveTextContent("5");
    expect(screen.getByTestId("stat-verified-steps")).toHaveTextContent("5");
    expect(screen.getByTestId("stat-failed-steps")).toHaveTextContent("0");
    expect(screen.getByTestId("stat-duration")).toHaveTextContent("5s");
    expect(screen.getByTestId("stat-target-url")).toHaveTextContent("http://localhost:3001");
  });
});

describe("RunDetailView", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading state initially and then displays run details", async () => {
    const fakeClient = new apiModule.MockApiClient();

    render(<RunDetailView runId="run-1" client={fakeClient} />);

    expect(screen.getByTestId("run-details-loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByTestId("run-details-loading")).not.toBeInTheDocument();
    });

    expect(screen.getByTestId("run-detail-prompt")).toBeInTheDocument();
    expect(screen.getByTestId("step-evidence-list")).toBeInTheDocument();
    expect(screen.getByTestId("step-evidence-card-1")).toBeInTheDocument();
  });

  it("renders not-found error state when run does not exist", async () => {
    const fakeClient = new apiModule.MockApiClient();

    render(<RunDetailView runId="unknown-run" client={fakeClient} />);

    await waitFor(() => {
      expect(screen.getByTestId("run-not-found")).toBeInTheDocument();
    });

    expect(screen.getByText("Run Not Found")).toBeInTheDocument();
    expect(screen.getByTestId("back-to-runs-button")).toBeInTheDocument();
  });

  it("renders initialDetails synchronously without loading spinner", () => {
    render(<RunDetailView runId="run-1" initialDetails={mockRunDetails["run-1"]} />);

    expect(screen.queryByTestId("run-details-loading")).not.toBeInTheDocument();
    expect(screen.getByTestId("run-detail-prompt")).toHaveTextContent(mockRunDetails["run-1"].run.prompt);
    expect(screen.getByTestId("step-evidence-list")).toBeInTheDocument();
  });
});

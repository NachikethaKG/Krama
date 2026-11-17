import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VersionHistoryPanel } from "@/components/versions/VersionHistoryPanel";
import { MockApiClient } from "@/lib/api";
import type { WorkflowVersionRecord } from "@/types/tutorial";

describe("VersionHistoryPanel Component Suite", () => {
  it("renders baseline state cleanly when only v1.0 exists without broken diff controls", async () => {
    const client = new MockApiClient();
    render(<VersionHistoryPanel workflowId="baseline-only" apiClient={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("version-history-baseline")).toBeInTheDocument();
    });

    expect(screen.getByText("Baseline version (v1.0)")).toBeInTheDocument();
    expect(screen.queryByTestId("view-diff-btn")).not.toBeInTheDocument();
  });

  it("handles failed API request gracefully with error message without crashing", async () => {
    const client = new MockApiClient();
    render(<VersionHistoryPanel workflowId="error-workflow" apiClient={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("version-history-error")).toBeInTheDocument();
    });

    expect(screen.getByText(/Unable to load version history/i)).toBeInTheDocument();
  });

  it("excludes heal_pending / pending_review versions from active list and isolates them in locked section (D8)", () => {
    const versions: WorkflowVersionRecord[] = [
      {
        id: "v-3",
        version: "v1.2",
        status: "heal_pending",
        changeSummary: "Pending review locator heal on submit button",
        isWordingOnly: false,
        createdAt: "2026-11-04T12:00:00Z",
        stepDiffs: [
          {
            stepIndex: 3,
            stepTitle: "Submit step",
            changeType: "locator_healed",
            oldSelector: "#submit",
            newSelector: ".submit-btn",
          },
        ],
      },
      {
        id: "v-2",
        version: "v1.1",
        status: "auto-updated",
        changeSummary: "Deterministic heal: updated primary button locator",
        isWordingOnly: false,
        createdAt: "2026-11-02T09:15:00Z",
        stepDiffs: [
          {
            stepIndex: 2,
            stepTitle: "Click Create Repository button",
            changeType: "locator_healed",
            oldSelector: "#old-btn",
            newSelector: "#new-btn",
          },
        ],
      },
      {
        id: "v-1",
        version: "v1.0",
        status: "archived",
        changeSummary: "Initial baseline version.",
        isWordingOnly: false,
        createdAt: "2026-10-11T08:00:00Z",
        stepDiffs: [],
      },
    ];

    render(<VersionHistoryPanel versions={versions} />);

    // Active version records list contains only playable versions
    const activeRecords = screen.getByTestId("version-records-list");
    expect(activeRecords).toHaveTextContent("v1.1");
    expect(activeRecords).toHaveTextContent("v1.0");
    expect(activeRecords).not.toHaveTextContent("v1.2");

    // Pending review section isolates v1.2 with locked badge
    expect(screen.getByTestId("pending-review-section")).toBeInTheDocument();
    expect(screen.getByTestId("pending-review-badge")).toHaveTextContent("Locked (Pending Review)");
    expect(screen.getByTestId("pending-version-item")).toHaveTextContent("v1.2");
  });

  it("collapses wording-only changes by default behind toggle and expands on click (D11)", () => {
    const versions: WorkflowVersionRecord[] = [
      {
        id: "v-wording-1",
        version: "v1.2",
        status: "active",
        changeSummary: "Updated introductory step caption for clarity",
        isWordingOnly: true,
        createdAt: "2026-11-03T10:00:00Z",
        stepDiffs: [
          {
            stepIndex: 1,
            stepTitle: "Navigate step",
            changeType: "wording_only",
            oldCaption: "Old caption",
            newCaption: "New clearer caption",
          },
        ],
      },
      {
        id: "v-healed-1",
        version: "v1.1",
        status: "auto-updated",
        changeSummary: "Healed primary button selector",
        isWordingOnly: false,
        createdAt: "2026-11-02T09:15:00Z",
        stepDiffs: [
          {
            stepIndex: 2,
            stepTitle: "Button click",
            changeType: "locator_healed",
            oldSelector: "#old",
            newSelector: "#new",
          },
        ],
      },
      {
        id: "v-init-1",
        version: "v1.0",
        status: "archived",
        changeSummary: "Baseline recording",
        isWordingOnly: false,
        createdAt: "2026-10-11T08:00:00Z",
        stepDiffs: [],
      },
    ];

    render(<VersionHistoryPanel versions={versions} />);

    // Toggle button should be visible showing wording-only count 1
    const toggle = screen.getByTestId("toggle-wording-changes");
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveTextContent("Wording-only changes (1)");

    // By default, wording-only version is collapsed
    expect(screen.queryByTestId("wording-versions-list")).not.toBeInTheDocument();

    // Click disclosure toggle to expand
    fireEvent.click(toggle);

    // Expanded list now visible
    expect(screen.getByTestId("wording-versions-list")).toBeInTheDocument();
    expect(screen.getByTestId("wording-version-item")).toHaveTextContent("v1.2");
    expect(screen.getByTestId("wording-version-item")).toHaveTextContent(
      "Updated introductory step caption for clarity"
    );

    // Click again to collapse
    fireEvent.click(toggle);
    expect(screen.queryByTestId("wording-versions-list")).not.toBeInTheDocument();
  });

  it("opens inline step diff modal preview on Inspect Step Diff click and closes on button click", () => {
    const versions: WorkflowVersionRecord[] = [
      {
        id: "v-healed-1",
        version: "v1.1",
        status: "auto-updated",
        changeSummary: "Healed primary button selector",
        isWordingOnly: false,
        createdAt: "2026-11-02T09:15:00Z",
        stepDiffs: [
          {
            stepIndex: 2,
            stepTitle: "Button click",
            changeType: "locator_healed",
            oldSelector: "#old",
            newSelector: "#new",
          },
        ],
      },
    ];

    render(<VersionHistoryPanel versions={versions} />);

    const inspectBtn = screen.getByTestId("view-diff-btn");
    fireEvent.click(inspectBtn);

    // Modal opens
    expect(screen.getByTestId("inspect-diff-modal")).toBeInTheDocument();
    expect(screen.getByTestId("step-diff-viewer")).toBeInTheDocument();
    expect(screen.getByTestId("diff-old-selector")).toHaveTextContent("#old");
    expect(screen.getByTestId("diff-new-selector")).toHaveTextContent("#new");

    // Close modal
    const closeBtn = screen.getByTestId("close-diff-modal-btn");
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId("inspect-diff-modal")).not.toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepDiffViewer } from "@/components/versions/StepDiffViewer";
import type { StepDiffItem } from "@/types/tutorial";

describe("StepDiffViewer Component Suite", () => {
  it("renders empty state message when diff list is empty", () => {
    render(<StepDiffViewer diffs={[]} />);

    const empty = screen.getByTestId("step-diff-empty");
    expect(empty).toBeInTheDocument();
    expect(empty).toHaveTextContent(/No differences found/i);
  });

  it("highlights modified steps with rose strikethrough old selector vs emerald new selector", () => {
    const diffs: StepDiffItem[] = [
      {
        stepIndex: 1,
        stepTitle: "Navigate to Dashboard",
        changeType: "unchanged",
      },
      {
        stepIndex: 2,
        stepTitle: "Click Create Repository button",
        changeType: "locator_healed",
        oldSelector: "button#old-repo-btn",
        newSelector: "button#new-create-repo-btn",
        oldLabel: "New Repository",
        newLabel: "Create Repository",
        oldCaption: "Click the old button.",
        newCaption: "Click the primary create button.",
      },
    ];

    render(
      <StepDiffViewer
        diffs={diffs}
        fromVersion="v1.0"
        toVersion="v1.1"
        changeSummary="Updated primary button locator to match redesigned UI."
      />
    );

    // Assert version compare header
    expect(screen.getByTestId("diff-version-comparison")).toHaveTextContent("v1.0→v1.1");
    expect(screen.getByTestId("diff-change-summary")).toHaveTextContent(
      "Updated primary button locator to match redesigned UI."
    );

    // Assert unchanged step is rendered compact
    const items = screen.getAllByTestId("step-diff-item");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveAttribute("data-change-type", "unchanged");
    expect(items[0]).toHaveTextContent("Unchanged");

    // Assert healed step highlights
    expect(items[1]).toHaveAttribute("data-change-type", "locator_healed");
    expect(screen.getByText("Locator Healed")).toBeInTheDocument();

    const oldSel = screen.getByTestId("diff-old-selector");
    expect(oldSel).toHaveTextContent("button#old-repo-btn");
    expect(oldSel).toHaveClass("line-through");
    expect(oldSel).toHaveClass("text-rose-700");

    const newSel = screen.getByTestId("diff-new-selector");
    expect(newSel).toHaveTextContent("button#new-create-repo-btn");
    expect(newSel).toHaveClass("text-emerald-800");

    const oldLbl = screen.getByTestId("diff-old-label");
    expect(oldLbl).toHaveTextContent("New Repository");
    expect(oldLbl).toHaveClass("line-through");

    const newLbl = screen.getByTestId("diff-new-label");
    expect(newLbl).toHaveTextContent("Create Repository");

    const oldCap = screen.getByTestId("diff-old-caption");
    expect(oldCap).toHaveTextContent("Click the old button.");

    const newCap = screen.getByTestId("diff-new-caption");
    expect(newCap).toHaveTextContent("Click the primary create button.");
  });

  it("renders wording-only changes cleanly with caption diffs", () => {
    const wordingDiffs: StepDiffItem[] = [
      {
        stepIndex: 1,
        stepTitle: "Fill repository name input",
        changeType: "wording_only",
        oldCaption: "Enter repo name in the field.",
        newCaption: "Enter repository name conforming to kebab-case convention.",
      },
    ];

    render(
      <StepDiffViewer
        diffs={wordingDiffs}
        fromVersion="v1.1"
        toVersion="v1.2"
      />
    );

    const item = screen.getByTestId("step-diff-item");
    expect(item).toHaveAttribute("data-change-type", "wording_only");
    expect(screen.getByText("Wording Changed")).toBeInTheDocument();

    expect(screen.getByTestId("diff-old-caption")).toHaveTextContent(
      "Enter repo name in the field."
    );
    expect(screen.getByTestId("diff-new-caption")).toHaveTextContent(
      "Enter repository name conforming to kebab-case convention."
    );
  });
});

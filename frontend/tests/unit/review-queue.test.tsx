import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ReviewQueueView } from "@/components/reviews/ReviewQueueView";
import { ReviewQueueItemCard } from "@/components/reviews/ReviewQueueItemCard";
import { mockReviewQueueItems } from "@/lib/fixtures";
import type { ApiClient } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/dashboard/reviews",
  useSearchParams: () => new URLSearchParams(),
}));

describe("ReviewQueue Unit Suite", () => {
  it("renders step diff when inspect diff button is clicked", () => {
    const healPendingItem = mockReviewQueueItems.find((i) => i.category === "heal_pending")!;
    render(<ReviewQueueItemCard item={healPendingItem} />);

    // In default state for heal_pending it's expanded
    expect(screen.getByTestId("step-diff-viewer")).toBeInTheDocument();

    // Toggle off
    const toggleBtn = screen.getByTestId("inspect-diff-btn");
    fireEvent.click(toggleBtn);
    expect(screen.queryByTestId("step-diff-viewer")).not.toBeInTheDocument();

    // Toggle on
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("step-diff-viewer")).toBeInTheDocument();
  });

  it("handles 429 quota error gracefully on Retry AI Fix", async () => {
    const mockRetryAiFix = vi.fn().mockRejectedValue(new Error("Daily AI fix quota reached (5/day)."));
    const mockClient: Partial<ApiClient> = {
      retryAiFix: mockRetryAiFix,
      getReviewQueue: vi.fn().mockResolvedValue(mockReviewQueueItems),
      getReviewQueueCount: vi.fn().mockResolvedValue({ count: mockReviewQueueItems.length }),
    };

    render(<ReviewQueueView initialItems={mockReviewQueueItems} client={mockClient as ApiClient} />);

    const retryBtns = screen.getAllByTestId("action-retry-ai-fix");
    expect(retryBtns.length).toBeGreaterThan(0);

    fireEvent.click(retryBtns[0]);

    await waitFor(() => {
      expect(mockRetryAiFix).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByTestId("quota-exhausted-notice")).toBeInTheDocument();
    });
  });
});

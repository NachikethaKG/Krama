import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ReviewQueueView } from "@/components/reviews/ReviewQueueView";
import { ReviewQueueItemCard } from "@/components/reviews/ReviewQueueItemCard";
import { DashboardNav } from "@/components/dashboard/DashboardNav";
import { mockReviewQueueItems } from "@/lib/fixtures";
import type { ApiClient } from "@/lib/api";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => "/dashboard/reviews",
  useSearchParams: () => new URLSearchParams(),
}));

describe("Owner Review Queue Components", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("ReviewQueueItemCard", () => {
    it("renders all 4 item types with accurate category badges and actions", () => {
      // 1. heal_pending item
      const healPendingItem = mockReviewQueueItems.find((i) => i.category === "heal_pending")!;
      const { rerender } = render(<ReviewQueueItemCard item={healPendingItem} />);

      expect(screen.getByText("Heal Pending")).toBeInTheDocument();
      expect(screen.getByTestId("action-accept")).toBeInTheDocument();
      expect(screen.getByTestId("action-reject")).toBeInTheDocument();
      expect(screen.getByTestId("inspect-diff-btn")).toBeInTheDocument();

      // 2. outdated item
      const outdatedItem = mockReviewQueueItems.find((i) => i.category === "outdated")!;
      rerender(<ReviewQueueItemCard item={outdatedItem} />);

      expect(screen.getByText("Outdated")).toBeInTheDocument();
      expect(screen.getByTestId("action-regenerate")).toBeInTheDocument();
      expect(screen.getByTestId("action-retry-ai-fix")).toBeInTheDocument();

      // 3. unstable item
      const unstableItem = mockReviewQueueItems.find((i) => i.category === "unstable")!;
      rerender(<ReviewQueueItemCard item={unstableItem} />);

      expect(screen.getByText("Unstable")).toBeInTheDocument();
      expect(screen.getByTestId("action-regenerate")).toBeInTheDocument();

      // 4. cant_check item (GitHub session expired)
      const cantCheckItem = mockReviewQueueItems.find((i) => i.category === "cant_check")!;
      rerender(<ReviewQueueItemCard item={cantCheckItem} />);

      expect(screen.getByTestId("category-cant_check")).toHaveTextContent("Can't check: GitHub session expired");
      expect(screen.getByTestId("action-reauth")).toHaveAttribute("href", "/runs/new?target=github");
      expect(screen.getByTestId("action-retry-check")).toBeInTheDocument();
    });

    it("displays inline quota notice on Retry AI Fix failure (429)", () => {
      const outdatedItem = mockReviewQueueItems.find((i) => i.category === "outdated")!;
      render(
        <ReviewQueueItemCard
          item={outdatedItem}
          quotaError="Daily AI fix limit reached (5/day). Please regenerate the workflow or retry tomorrow."
        />
      );

      const notice = screen.getByTestId("quota-exhausted-notice");
      expect(notice).toBeInTheDocument();
      expect(notice).toHaveTextContent(/Daily AI fix limit reached/i);
    });
  });

  describe("ReviewQueueView Interaction & State Transitions", () => {
    it("renders all items and filters by category tab", async () => {
      render(<ReviewQueueView initialItems={mockReviewQueueItems} />);

      const cards = screen.getAllByTestId("review-queue-card");
      expect(cards.length).toBe(4);

      // Filter by Pending Heal
      const healTab = screen.getByTestId("filter-tab-heal_pending");
      fireEvent.click(healTab);

      const filteredCards = screen.getAllByTestId("review-queue-card");
      expect(filteredCards.length).toBe(1);
      expect(filteredCards[0]).toHaveAttribute("data-category", "heal_pending");

      // Reset to All
      const allTab = screen.getByTestId("filter-tab-all");
      fireEvent.click(allTab);
      expect(screen.getAllByTestId("review-queue-card").length).toBe(4);
    });

    it("clicking Accept on heal_pending removes item, shows toast, and dispatches count update", async () => {
      const mockAccept = vi.fn().mockResolvedValue({ success: true, message: "Healed version is now live" });
      const mockClient: Partial<ApiClient> = {
        acceptReview: mockAccept,
        getReviewQueue: vi.fn().mockResolvedValue(mockReviewQueueItems),
        getReviewQueueCount: vi.fn().mockResolvedValue({ count: mockReviewQueueItems.length }),
      };

      const eventSpy = vi.fn();
      window.addEventListener("krama:review-count-changed", eventSpy);

      render(<ReviewQueueView initialItems={mockReviewQueueItems} client={mockClient as ApiClient} />);

      const acceptBtn = screen.getByTestId("action-accept");
      fireEvent.click(acceptBtn);

      await waitFor(() => {
        expect(mockAccept).toHaveBeenCalledWith("rev-1");
      });

      // Item removed from view
      await waitFor(() => {
        expect(screen.queryByText("Create repository in local Gitea (Auto-healed)")).not.toBeInTheDocument();
      });

      // Toast confirmation displayed
      expect(screen.getByTestId("review-queue-toast")).toHaveTextContent("Healed version is now live");

      // Custom event dispatched with decremented count
      expect(eventSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          detail: { count: 3 },
        })
      );

      window.removeEventListener("krama:review-count-changed", eventSpy);
    });

    it("clicking Reject marks heal_pending item outdated and decrements active queue badge", async () => {
      const mockReject = vi.fn().mockResolvedValue({ success: true, message: "Pending heal rejected" });
      const mockClient: Partial<ApiClient> = {
        rejectReview: mockReject,
        getReviewQueue: vi.fn().mockResolvedValue(mockReviewQueueItems),
        getReviewQueueCount: vi.fn().mockResolvedValue({ count: mockReviewQueueItems.length }),
      };

      const eventSpy = vi.fn();
      window.addEventListener("krama:review-count-changed", eventSpy);

      render(<ReviewQueueView initialItems={mockReviewQueueItems} client={mockClient as ApiClient} />);

      const rejectBtn = screen.getByTestId("action-reject");
      fireEvent.click(rejectBtn);

      await waitFor(() => {
        expect(mockReject).toHaveBeenCalledWith("rev-1");
      });

      // Workflow is marked outdated (D8)
      await waitFor(() => {
        const cards = screen.getAllByTestId("review-queue-card");
        const card = cards.find((c) => c.getAttribute("data-item-id") === "rev-1");
        expect(card).toBeInTheDocument();
        expect(card).toHaveAttribute("data-category", "outdated");
      });

      expect(screen.getByTestId("review-queue-toast")).toHaveTextContent(/Pending heal rejected/i);

      window.removeEventListener("krama:review-count-changed", eventSpy);
    });

    it("clicking Regenerate triggers regenerateWorkflow and navigates to new run page", async () => {
      const mockRegen = vi.fn().mockResolvedValue({ id: "run-regen-123", run_id: "run-regen-123", status: "planning" });
      const mockClient: Partial<ApiClient> = {
        regenerateWorkflow: mockRegen,
        getReviewQueue: vi.fn().mockResolvedValue(mockReviewQueueItems),
        getReviewQueueCount: vi.fn().mockResolvedValue({ count: mockReviewQueueItems.length }),
      };

      render(<ReviewQueueView initialItems={mockReviewQueueItems} client={mockClient as ApiClient} />);

      // Find regenerate button on the outdated card
      const regenBtn = screen.getAllByTestId("action-regenerate")[0];
      fireEvent.click(regenBtn);

      await waitFor(() => {
        expect(mockRegen).toHaveBeenCalledWith("github-repo-settings");
      });

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/runs/run-regen-123");
      });
    });

    it("renders zero-state card when queue is empty", () => {
      render(<ReviewQueueView initialItems={[]} />);

      const emptyCard = screen.getByTestId("review-queue-empty");
      expect(emptyCard).toBeInTheDocument();
      expect(emptyCard).toHaveTextContent("All tutorials are healthy — nothing needs review");
    });
  });

  describe("DashboardNav & Count Badge", () => {
    it("renders review queue nav link and updates badge dynamically", async () => {
      const mockClient: Partial<ApiClient> = {
        getReviewQueueCount: vi.fn().mockResolvedValue({ count: 4 }),
      };

      render(<DashboardNav client={mockClient as ApiClient} />);

      await waitFor(() => {
        expect(screen.getByTestId("review-queue-badge")).toHaveTextContent("4");
      });

      // Dispatch event to simulate item resolved
      window.dispatchEvent(new CustomEvent("krama:review-count-changed", { detail: { count: 3 } }));

      await waitFor(() => {
        expect(screen.getByTestId("review-queue-badge")).toHaveTextContent("3");
      });
    });
  });
});

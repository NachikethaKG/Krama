import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TutorialCard, TutorialLibraryView, TutorialSearchFilter } from "@/components/tutorials";
import { MockApiClient } from "@/lib/api";
import { mockTutorialSummaries } from "@/lib/fixtures";
import type { TutorialSummary } from "@/types/tutorial";

describe("Tutorial Library Component Suite", () => {
  describe("TutorialCard", () => {
    const sampleTutorial: TutorialSummary = {
      id: "test-tutorial-1",
      title: "Create a repository in local Gitea",
      description: "Initialize and configure a new Git repository with README and license in local Gitea.",
      taskPrompt: "Create a repository in local Gitea",
      target: "gitea",
      status: "verified",
      stepCount: 5,
      durationMs: 90000,
      createdAt: "2026-10-06T12:00:00.000Z",
    };

    it("renders title, description, target badge, status badge, step count, duration, and link", () => {
      render(<TutorialCard tutorial={sampleTutorial} />);

      expect(screen.getByText("Create a repository in local Gitea")).toBeInTheDocument();
      expect(
        screen.getByText(/Initialize and configure a new Git repository/i),
      ).toBeInTheDocument();

      const targetBadge = screen.getByTestId("tutorial-card-target");
      expect(targetBadge).toHaveTextContent("Gitea");
      expect(targetBadge).toHaveAttribute("data-target", "gitea");

      const statusBadge = screen.getByTestId("tutorial-card-status");
      expect(statusBadge).toHaveTextContent("Verified");
      expect(statusBadge).toHaveAttribute("data-status", "verified");

      const meta = screen.getByTestId("tutorial-card-meta");
      expect(meta).toHaveTextContent("5 steps");
      expect(meta).toHaveTextContent("~2 min");
      expect(meta).toHaveTextContent("Oct 6, 2026");

      const openLink = screen.getByTestId("tutorial-card-open");
      expect(openLink).toHaveAttribute("href", "/tutorials/test-tutorial-1");
      expect(openLink).toHaveTextContent("Open Tutorial");
    });

    it("renders outdated status badge and GitHub target badge correctly", () => {
      const outdatedGithub: TutorialSummary = {
        id: "github-outdated-1",
        title: "Delete repository on GitHub",
        target: "github",
        status: "outdated",
        stepCount: 3,
        durationMs: 40000,
        createdAt: "2026-09-15T00:00:00.000Z",
      };

      render(<TutorialCard tutorial={outdatedGithub} />);

      const targetBadge = screen.getByTestId("tutorial-card-target");
      expect(targetBadge).toHaveTextContent("GitHub");
      expect(targetBadge).toHaveAttribute("data-target", "github");

      const statusBadge = screen.getByTestId("tutorial-card-status");
      expect(statusBadge).toHaveTextContent("Outdated");
      expect(statusBadge).toHaveAttribute("data-status", "outdated");

      const meta = screen.getByTestId("tutorial-card-meta");
      expect(meta).toHaveTextContent("3 steps");
      expect(meta).toHaveTextContent("< 1 min");
    });

    it("renders custom target platform badge", () => {
      const customTutorial: TutorialSummary = {
        id: "custom-1",
        title: "Export metrics from internal dashboard",
        target: "custom",
        status: "verified",
        stepCount: 4,
        durationMs: 60000,
        createdAt: "2026-10-18T00:00:00.000Z",
      };

      render(<TutorialCard tutorial={customTutorial} />);

      const targetBadge = screen.getByTestId("tutorial-card-target");
      expect(targetBadge).toHaveTextContent("Custom");
      expect(targetBadge).toHaveAttribute("data-target", "custom");
    });
  });

  describe("TutorialSearchFilter", () => {
    const counts = { all: 5, verified: 3, outdated: 2 };

    it("renders search input and status tabs with accurate counts", () => {
      const onSearchChange = vi.fn();
      const onStatusFilterChange = vi.fn();

      render(
        <TutorialSearchFilter
          searchQuery=""
          onSearchChange={onSearchChange}
          statusFilter="all"
          onStatusFilterChange={onStatusFilterChange}
          counts={counts}
        />,
      );

      const input = screen.getByTestId("tutorial-search-input");
      expect(input).toBeInTheDocument();

      const allTab = screen.getByTestId("filter-status-all");
      const verifiedTab = screen.getByTestId("filter-status-verified");
      const outdatedTab = screen.getByTestId("filter-status-outdated");

      expect(allTab).toHaveTextContent("All");
      expect(allTab).toHaveTextContent("5");
      expect(allTab).toHaveAttribute("aria-selected", "true");

      expect(verifiedTab).toHaveTextContent("Verified");
      expect(verifiedTab).toHaveTextContent("3");
      expect(verifiedTab).toHaveAttribute("aria-selected", "false");

      expect(outdatedTab).toHaveTextContent("Outdated");
      expect(outdatedTab).toHaveTextContent("2");
      expect(outdatedTab).toHaveAttribute("aria-selected", "false");
    });

    it("triggers callbacks when typing search query and switching status tabs", () => {
      const onSearchChange = vi.fn();
      const onStatusFilterChange = vi.fn();

      render(
        <TutorialSearchFilter
          searchQuery="git"
          onSearchChange={onSearchChange}
          statusFilter="verified"
          onStatusFilterChange={onStatusFilterChange}
          counts={counts}
        />,
      );

      const input = screen.getByTestId("tutorial-search-input");
      fireEvent.change(input, { target: { value: "gitea" } });
      expect(onSearchChange).toHaveBeenCalledWith("gitea");

      const clearBtn = screen.getByTestId("tutorial-search-clear");
      fireEvent.click(clearBtn);
      expect(onSearchChange).toHaveBeenCalledWith("");

      const outdatedTab = screen.getByTestId("filter-status-outdated");
      fireEvent.click(outdatedTab);
      expect(onStatusFilterChange).toHaveBeenCalledWith("outdated");
    });
  });

  describe("TutorialLibraryView", () => {
    it("renders list of tutorials fetched from mock API client", async () => {
      const client = new MockApiClient();
      render(<TutorialLibraryView client={client} />);

      // Initially shows loading or quickly renders
      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });

      const cards = screen.getAllByTestId("tutorial-card");
      expect(cards.length).toBe(mockTutorialSummaries.length);

      expect(screen.getByText("Create a repository in local Gitea")).toBeInTheDocument();
      expect(screen.getByText("Star a repository on GitHub")).toBeInTheDocument();
      expect(screen.getByText("Create an issue with template on GitHub")).toBeInTheDocument();
      expect(screen.getByText("Add deploy key in Gitea repository")).toBeInTheDocument();
      expect(screen.getByText("Export analytics report in Custom Portal")).toBeInTheDocument();
    });

    it("filters list in real time by search query", async () => {
      const client = new MockApiClient();
      render(<TutorialLibraryView client={client} />);

      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("tutorial-search-input");
      fireEvent.change(searchInput, { target: { value: "GitHub" } });

      const filteredCards = screen.getAllByTestId("tutorial-card");
      expect(filteredCards.length).toBe(2);
      expect(screen.getByText("Star a repository on GitHub")).toBeInTheDocument();
      expect(screen.getByText("Create an issue with template on GitHub")).toBeInTheDocument();
      expect(screen.queryByText("Create a repository in local Gitea")).not.toBeInTheDocument();
    });

    it("filters tutorials across task prompt text and description", async () => {
      const client = new MockApiClient();
      render(<TutorialLibraryView client={client} />);

      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("tutorial-search-input");
      // Search for keyword in prompt/description: "kubernetes"
      fireEvent.change(searchInput, { target: { value: "kubernetes" } });

      const filteredCards = screen.getAllByTestId("tutorial-card");
      expect(filteredCards.length).toBe(1);
      expect(screen.getByText("Star a repository on GitHub")).toBeInTheDocument();
    });

    it("toggles between All, Verified, and Outdated status tabs", async () => {
      const client = new MockApiClient();
      render(<TutorialLibraryView client={client} />);

      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });

      // Filter by Verified
      const verifiedTab = screen.getByTestId("filter-status-verified");
      fireEvent.click(verifiedTab);

      const verifiedCards = screen.getAllByTestId("tutorial-card");
      expect(verifiedCards.length).toBe(3);
      expect(screen.getByText("Create a repository in local Gitea")).toBeInTheDocument();
      expect(screen.getByText("Star a repository on GitHub")).toBeInTheDocument();
      expect(screen.getByText("Export analytics report in Custom Portal")).toBeInTheDocument();
      expect(screen.queryByText("Create an issue with template on GitHub")).not.toBeInTheDocument();

      // Filter by Outdated
      const outdatedTab = screen.getByTestId("filter-status-outdated");
      fireEvent.click(outdatedTab);

      const outdatedCards = screen.getAllByTestId("tutorial-card");
      expect(outdatedCards.length).toBe(2);
      expect(screen.getByText("Create an issue with template on GitHub")).toBeInTheDocument();
      expect(screen.getByText("Add deploy key in Gitea repository")).toBeInTheDocument();
      expect(screen.queryByText("Create a repository in local Gitea")).not.toBeInTheDocument();

      // Switch back to All
      const allTab = screen.getByTestId("filter-status-all");
      fireEvent.click(allTab);

      expect(screen.getAllByTestId("tutorial-card").length).toBe(5);
    });

    it("combines search query with status filter tab", async () => {
      const client = new MockApiClient();
      render(<TutorialLibraryView client={client} />);

      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });

      // Select Outdated tab
      const outdatedTab = screen.getByTestId("filter-status-outdated");
      fireEvent.click(outdatedTab);

      // Search for "Gitea"
      const searchInput = screen.getByTestId("tutorial-search-input");
      fireEvent.change(searchInput, { target: { value: "Gitea" } });

      const filteredCards = screen.getAllByTestId("tutorial-card");
      expect(filteredCards.length).toBe(1);
      expect(screen.getByText("Add deploy key in Gitea repository")).toBeInTheDocument();
      expect(screen.queryByText("Create a repository in local Gitea")).not.toBeInTheDocument();
    });

    it("displays empty state when no tutorials match query and resets filters on button click", async () => {
      const client = new MockApiClient();
      render(<TutorialLibraryView client={client} />);

      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("tutorial-search-input");
      fireEvent.change(searchInput, { target: { value: "nonexistent-query-12345" } });

      const emptyState = screen.getByTestId("empty-tutorials");
      expect(emptyState).toBeInTheDocument();
      expect(
        screen.getByText("No tutorials match your search"),
      ).toBeInTheDocument();

      const resetBtn = screen.getByTestId("reset-filters-btn");
      fireEvent.click(resetBtn);

      await waitFor(() => {
        expect(screen.getByTestId("tutorial-grid")).toBeInTheDocument();
      });
      expect(screen.getAllByTestId("tutorial-card").length).toBe(5);
    });

    it("displays friendly zero-state when API returns an empty list", async () => {
      class EmptyClient extends MockApiClient {
        override async getTutorials() {
          return [];
        }
      }

      render(<TutorialLibraryView client={new EmptyClient()} />);

      await waitFor(() => {
        expect(screen.getByTestId("empty-tutorials")).toBeInTheDocument();
      });

      expect(
        screen.getByText("No tutorials yet"),
      ).toBeInTheDocument();
      expect(screen.getByText("New tutorial")).toBeInTheDocument();
    });

    it("handles API failure gracefully with error alert banner and retry button", async () => {
      class ErrorClient extends MockApiClient {
        override async getTutorials(): Promise<TutorialSummary[]> {
          throw new Error("500 Internal Server Error: Database unreachable");
        }
      }

      render(<TutorialLibraryView client={new ErrorClient()} />);

      await waitFor(() => {
        expect(screen.getByTestId("tutorials-error")).toBeInTheDocument();
      });

      expect(screen.getByText("Couldn't load your tutorials")).toBeInTheDocument();
      expect(screen.getByText(/Database unreachable/i)).toBeInTheDocument();
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });
  });
});

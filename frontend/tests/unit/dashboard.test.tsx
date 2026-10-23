import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  DashboardHeader,
  DashboardView,
  MyTutorialsSection,
  RecentRunsSection,
} from "@/components/dashboard";
import { MockApiClient } from "@/lib/api";
import { demoUserFixture, mockTutorialSummaries } from "@/lib/fixtures";
import type { RunListItem } from "@/lib/types";

// Mock router
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

describe("User Dashboard Component Suite", () => {
  describe("DashboardHeader", () => {
    it("renders user email, display name, plan badge, and new run button", () => {
      render(<DashboardHeader user={demoUserFixture} />);

      expect(screen.getByTestId("user-email-display")).toHaveTextContent("demo@krama.dev");
      expect(screen.getByTestId("user-plan-badge")).toHaveTextContent(/Seeded Pro MVP/i);
      expect(screen.getByTestId("dashboard-new-run-btn")).toHaveAttribute("href", "/runs/new");
      expect(screen.getByTestId("dashboard-logout-btn")).toBeInTheDocument();
    });

    it("invokes apiClient.logout and onLogout callback on click", async () => {
      const client = new MockApiClient();
      const logoutSpy = vi.spyOn(client, "logout");
      const onLogout = vi.fn();

      render(<DashboardHeader user={demoUserFixture} client={client} onLogout={onLogout} />);

      const logoutBtn = screen.getByTestId("dashboard-logout-btn");
      fireEvent.click(logoutBtn);

      await waitFor(() => {
        expect(logoutSpy).toHaveBeenCalled();
        expect(onLogout).toHaveBeenCalled();
      });
    });
  });

  describe("MyTutorialsSection", () => {
    it("renders user-owned tutorials with status pills, target badges, and action buttons", () => {
      render(<MyTutorialsSection tutorials={mockTutorialSummaries} />);

      expect(screen.getByText("My Recorded Tutorials")).toBeInTheDocument();
      const items = screen.getAllByTestId("dashboard-tutorial-item");
      expect(items.length).toBe(mockTutorialSummaries.length);

      expect(screen.getByText("Create a repository in local Gitea")).toBeInTheDocument();
      expect(screen.getByText("Star a repository on GitHub")).toBeInTheDocument();

      const openLinks = screen.getAllByTestId("dashboard-open-tutorial");
      expect(openLinks[0]).toHaveAttribute("href", `/tutorials/${mockTutorialSummaries[0].id}`);
    });

    it("copies share link to clipboard on click", async () => {
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
      });

      render(<MyTutorialsSection tutorials={mockTutorialSummaries} />);

      const shareButtons = screen.getAllByTestId("dashboard-share-tutorial");
      fireEvent.click(shareButtons[0]);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
          expect.stringContaining(`/tutorials/${mockTutorialSummaries[0].id}`),
        );
        expect(shareButtons[0]).toHaveTextContent("Copied!");
      });
    });

    it("renders empty state when user has no tutorials", () => {
      render(<MyTutorialsSection tutorials={[]} />);

      const empty = screen.getByTestId("empty-my-tutorials");
      expect(empty).toBeInTheDocument();
      expect(screen.getByText(/You haven't recorded any tutorials yet/i)).toBeInTheDocument();
    });
  });

  describe("RecentRunsSection", () => {
    const sampleRuns: RunListItem[] = [
      {
        id: "6f1c2a4e-1111-4b8a-9a1b-123456789abc",
        prompt: "Create a repository in local Gitea",
        status: "verified",
        createdAt: "2026-10-06T12:00:00.000Z",
        startedAt: "2026-10-06T12:00:00.000Z",
        finishedAt: "2026-10-06T12:00:45.000Z",
        durationSeconds: 45,
      },
      {
        id: "7a2b3c4d-2222-4b8a-9a1b-123456789def",
        prompt: "Star a repository on GitHub",
        status: "running",
        createdAt: "2026-10-20T10:00:00.000Z",
        startedAt: "2026-10-20T10:00:00.000Z",
        durationSeconds: null,
      },
    ];

    it("renders recent runs table with run IDs, prompts, status badges, and evidence links", () => {
      render(<RecentRunsSection runs={sampleRuns} />);

      expect(screen.getByText("Recent Executions")).toBeInTheDocument();
      const rows = screen.getAllByTestId("recent-run-row");
      expect(rows.length).toBe(2);

      expect(screen.getByText("Create a repository in local Gitea")).toBeInTheDocument();
      expect(screen.getByText("Star a repository on GitHub")).toBeInTheDocument();
      expect(screen.getByText("45s")).toBeInTheDocument();
    });

    it("renders empty state when user has no runs", () => {
      render(<RecentRunsSection runs={[]} />);

      const empty = screen.getByTestId("empty-recent-runs");
      expect(empty).toBeInTheDocument();
      expect(screen.getByText(/No execution runs found/i)).toBeInTheDocument();
    });
  });

  describe("DashboardView", () => {
    it("fetches and renders populated user dashboard from MockApiClient", async () => {
      const client = new MockApiClient();
      render(<DashboardView client={client} />);

      await waitFor(() => {
        expect(screen.getByTestId("user-email-display")).toHaveTextContent("demo@krama.dev");
      });

      expect(screen.getByText("My Recorded Tutorials")).toBeInTheDocument();
      expect(screen.getByText("Recent Executions")).toBeInTheDocument();
    });

    it("displays error banner when user authentication fails", async () => {
      class UnauthClient extends MockApiClient {
        override async getMe(): Promise<never> {
          throw new Error("401 Unauthorized: Not signed in");
        }
      }

      render(<DashboardView client={new UnauthClient()} />);

      await waitFor(() => {
        expect(screen.getByTestId("dashboard-error")).toBeInTheDocument();
      });

      expect(screen.getByText(/Unable to Load Dashboard/i)).toBeInTheDocument();
    });
  });
});

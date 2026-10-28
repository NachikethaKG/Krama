import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HomeScreen } from "@/components/home/HomeScreen";
import { TutorialLibraryView, PAGE_SIZE } from "@/components/tutorials/TutorialLibraryView";
import { MockApiClient } from "@/lib/api";
import type { TutorialSummary } from "@/types/tutorial";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn(), back: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

function tutorials(n: number): TutorialSummary[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `t-${i + 1}`,
    title: `Tutorial ${i + 1}`,
    taskPrompt: `Tutorial ${i + 1}`,
    target: "github",
    status: "verified",
    stepCount: 3,
    durationMs: 20_000,
    createdAt: "2026-10-28T10:00:00Z",
  }));
}

class Client extends MockApiClient {
  constructor(private readonly items: TutorialSummary[]) {
    super();
  }
  override async getTutorials(): Promise<TutorialSummary[]> {
    return this.items;
  }
}

describe("Home screen (#318)", () => {
  it("asks what to learn and shows up to six recent tutorials", async () => {
    render(<HomeScreen client={new Client(tutorials(9))} />);

    expect(screen.getByLabelText("What do you want to learn?")).toBeInTheDocument();
    expect(screen.getByTestId("example-prompts")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByTestId("tutorial-card")).toHaveLength(6));
    expect(screen.queryByText(/Gitea/)).not.toBeInTheDocument();
  });

  it("says so when there are no tutorials yet", async () => {
    render(<HomeScreen client={new Client([])} />);
    expect(await screen.findByTestId("home-no-tutorials")).toBeInTheDocument();
  });
});

describe("My tutorials list (#318)", () => {
  it("shows the first page and more on request instead of everything at once", async () => {
    render(<TutorialLibraryView initialTutorials={tutorials(30)} />);

    expect(screen.getAllByTestId("tutorial-card")).toHaveLength(PAGE_SIZE);
    fireEvent.click(screen.getByTestId("tutorials-show-more"));
    expect(screen.getAllByTestId("tutorial-card")).toHaveLength(2 * PAGE_SIZE);
    fireEvent.click(screen.getByTestId("tutorials-show-more"));
    expect(screen.getAllByTestId("tutorial-card")).toHaveLength(30);
    expect(screen.queryByTestId("tutorials-show-more")).not.toBeInTheDocument();
  });
});

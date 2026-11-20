import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MarkedText } from "@/components/tutorials/TutorialCard";
import { TutorialLibraryView } from "@/components/tutorials/TutorialLibraryView";
import { HttpApiClient, MockApiClient } from "@/lib/api";

describe("library search (#419)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("marks matched words and shows everything else as text, never HTML", () => {
    const { container } = render(<MarkedText text={'Click <mark>Webhooks</mark> <img src=x onerror="alert(1)">'} />);

    expect(container.querySelectorAll("mark")).toHaveLength(1);
    expect(container.querySelector("mark")).toHaveTextContent("Webhooks");
    expect(container.querySelector("img")).toBeNull();
    expect(container).toHaveTextContent('<img src=x onerror="alert(1)">');
  });

  it("asks the server with the typed words and the status filter", async () => {
    const client = new MockApiClient();
    const search = vi.spyOn(client, "searchTutorials");
    render(<TutorialLibraryView client={client} />);
    await screen.findByTestId("tutorial-grid");

    fireEvent.click(screen.getByTestId("filter-status-verified"));
    fireEvent.change(screen.getByTestId("tutorial-search-input"), { target: { value: "star repo" } });

    await waitFor(() => expect(search).toHaveBeenCalledWith("star repo", { status: "verified" }));
    await waitFor(() => expect(screen.queryByTestId("library-searching")).toBeNull());
    expect(screen.getByTestId("tutorial-snippet").querySelectorAll("mark").length).toBeGreaterThan(0);
  });

  it("sends q, status and limit and maps the match to the card", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "w1",
              title: "Add a webhook",
              status: "verified",
              step_count: 4,
              target_app: "gitea",
              score: 1.2,
              match: { step_seq: 2, snippet: "Click <mark>Webhooks</mark>." },
            },
          ],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const [hit] = await new HttpApiClient("http://api/api/v1").searchTutorials("web hooks", { status: "outdated" });

    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/v1/workflows");
    expect(Object.fromEntries(url.searchParams)).toEqual({ q: "web hooks", limit: "30", status: "outdated" });
    expect(hit).toMatchObject({ id: "w1", title: "Add a webhook", snippet: "Click <mark>Webhooks</mark>.", matchStep: 2 });
  });
});

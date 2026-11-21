import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import { DoItForMeModal, previewText, refusalMessage } from "@/components/do-it";
import type { DoItText } from "@/components/do-it/DoItForMeModal";
import { FailureBanner } from "@/components/execution/failure-banner";
import { createTranslator } from "next-intl";
import { ApiRequestError, HttpApiClient, MockApiClient, inputProblem } from "@/lib/api";
import doItMessages from "@/messages/en/doIt.json";
import { giteaWorkflowFixture, giteaWorkflowInputsFixture } from "@/lib/fixtures";

const WORKFLOW_ID = giteaWorkflowFixture.id;

function open(client = new MockApiClient(), workflowId = WORKFLOW_ID) {
  render(<DoItForMeModal isOpen onClose={vi.fn()} workflowId={workflowId} client={client} />);
}

describe("DoItForMeModal (#402)", () => {
  beforeEach(() => push.mockReset());

  it("asks for the user's own value, with the recorded one only as an example", async () => {
    open();

    const field = await screen.findByLabelText("Repository name");
    expect(field).toHaveValue("");
    expect(field).toHaveAttribute("placeholder", "for example demo-repo");
    expect(screen.getByTestId("do-it-account")).toHaveTextContent("your demo account");
  });

  it("shows the steps with the user's value and runs them", async () => {
    open();
    const field = await screen.findByLabelText("Repository name");

    fireEvent.change(field, { target: { value: "team-notes" } });

    expect(screen.getByTestId("do-it-preview-step-3")).toHaveTextContent("Enter team-notes as the repository name.");
    fireEvent.click(screen.getByTestId("do-it-run-btn"));
    await waitFor(() => expect(push).toHaveBeenCalledWith(`/runs/run-do-it-${WORKFLOW_ID}/live`));
  });

  it("refuses a value outside the example's characters before calling the server", async () => {
    const client = new MockApiClient();
    const run = vi.spyOn(client, "runWorkflow");
    open(client);
    const field = await screen.findByLabelText("Repository name");

    fireEvent.change(field, { target: { value: "team notes" } });
    fireEvent.click(screen.getByTestId("do-it-run-btn"));

    expect(await screen.findByText(/same kind of characters/)).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(run).not.toHaveBeenCalled();
  });

  it("shows the server's input_unsafe answer on its field", async () => {
    const client = new MockApiClient();
    vi.spyOn(client, "runWorkflow").mockRejectedValue(
      new ApiRequestError("422", 422, {
        code: "validation_error",
        message: "Repository name is already used",
        details: { reason: "input_unsafe", key: "repository_name" },
      }),
    );
    open(client);
    fireEvent.change(await screen.findByLabelText("Repository name"), { target: { value: "team-notes" } });

    fireEvent.click(screen.getByTestId("do-it-run-btn"));

    expect(await screen.findByText("Repository name is already used")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("explains why a workflow can't run for the user", async () => {
    open(new MockApiClient(), "github-create-issue-outdated");

    expect(await screen.findByTestId("do-it-refused")).toHaveTextContent("Only a verified tutorial can run for you");
    expect(screen.getByTestId("do-it-run-btn")).toBeDisabled();
  });

  it("asks the user to sign in to the site first and starts a sign-in run (#404)", async () => {
    const client = new MockApiClient();
    vi.spyOn(client, "getWorkflowInputs").mockResolvedValue({
      ...giteaWorkflowInputsFixture,
      account: null,
      sign_in_site: "gitea",
    });
    const signIn = vi.spyOn(client, "startSignIn");
    open(client);

    expect(await screen.findByTestId("do-it-sign-in")).toHaveTextContent("Sign in to gitea first");
    expect(screen.getByTestId("do-it-run-btn")).toBeDisabled();
    fireEvent.click(screen.getByTestId("do-it-sign-in-btn"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/runs/run-sign-in-gitea/live"));
    expect(signIn).toHaveBeenCalledWith("gitea");
  });

  it("marks the steps that will pause for the user's confirmation", async () => {
    const client = new MockApiClient();
    const risky = {
      ...giteaWorkflowFixture,
      steps: giteaWorkflowFixture.steps.map((s) => (s.seq === 5 ? { ...s, risk: "high" as const } : s)),
    };
    vi.spyOn(client, "getWorkflow").mockResolvedValue(risky);
    open(client);

    expect(await screen.findByTestId("do-it-pauses-5")).toHaveTextContent("Asks you first");
    expect(screen.queryByTestId("do-it-pauses-3")).toBeNull();
  });
});

describe("do it for me helpers", () => {
  it("swaps whole words only in the preview", () => {
    expect(previewText("Open main, not maintenance.", { main: "dev" })).toBe("Open dev, not maintenance.");
    expect(previewText("Enter demo-repo.", { "demo-repo": "" })).toBe("Enter demo-repo.");
  });

  it("checks values like the server", () => {
    const [input] = giteaWorkflowInputsFixture.inputs;
    expect(inputProblem(input, "team-notes")).toBeNull();
    expect(inputProblem(input, "ab")).toMatch(/at least 3/);
    expect(inputProblem(input, " team")).toMatch(/one line/);
    expect(inputProblem(input, undefined)).toMatch(/missing/);
  });

  it("words each refusal reason", () => {
    const refused = (details: Record<string, unknown>) =>
      refusalMessage(
        new ApiRequestError("409", 409, { code: "conflict", message: "x", details }),
        createTranslator({ locale: "en", messages: { doIt: doItMessages }, namespace: "doIt" }) as unknown as DoItText,
      );
    expect(refused({ reason: "secret_not_stored", step_seq: 2 })).toMatch(/^Step 2 types a password/);
    expect(refused({ reason: "pending_review" })).toMatch(/waits for your review/);
    expect(refused({ reason: "stale_revision" })).toMatch(/changed since you opened it/);
  });
});

describe("HttpApiClient do it for me routes", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads the inputs and starts the run with the previewed revision", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(giteaWorkflowInputsFixture)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "r1", kind: "do_it" }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new HttpApiClient("http://api/api/v1");

    await client.getWorkflowInputs("w 1");
    await client.runWorkflow("w 1", 1, { repository_name: "team-notes" });

    expect(fetchMock.mock.calls[0][0]).toBe("http://api/api/v1/workflows/w%201/inputs");
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("http://api/api/v1/workflows/w%201/run");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ revision: 1, inputs: { repository_name: "team-notes" } });
  });
});

describe("FailureBanner for a do it for me run", () => {
  it("says what ran and offers a fresh plan instead of the plan page", () => {
    render(
      <FailureBanner
        error={{ code: "internal", message: "Step 4 failed" }}
        doIt={{ done: 3, total: 5, planFreshHref: "/?prompt=Create%20a%20repository" }}
      />,
    );

    expect(screen.getByTestId("do-it-progress")).toHaveTextContent("3 of 5 steps ran");
    expect(screen.getByTestId("plan-it-fresh-btn")).toHaveAttribute("href", "/?prompt=Create%20a%20repository");
    expect(screen.queryByTestId("back-to-plan-btn")).toBeNull();
  });
});

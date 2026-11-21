import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Translation } from "@krama/contracts-ts";

import { ExportVideoModal } from "@/components/export";
import { applyTranslation, WorkflowTutorial } from "@/components/player/WorkflowTutorial";
import { selectOptimalVoice } from "@/components/player/useStepNarration";
import { MockApiClient } from "@/lib/api";
import * as api from "@/lib/api";
import { giteaWorkflowFixture } from "@/lib/fixtures";

const voice = (lang: string, name: string, localService = false) =>
  ({ lang, name, localService, default: false, voiceURI: name }) as SpeechSynthesisVoice;

function translation(status: Translation["status"], partly = false): Translation {
  return {
    workflow_id: giteaWorkflowFixture.id,
    revision: 1,
    language: "de",
    status,
    title: "Ein Repository erstellen",
    steps: giteaWorkflowFixture.steps.map((s, i) => ({
      step_seq: s.seq,
      text: partly && i === 0 ? s.instruction_text : `DE: ${s.instruction_text}`,
      translated: !(partly && i === 0),
    })),
  };
}

describe("tutorial language (#427)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("narrates in the tutorial's language, or not at all", () => {
    const voices = [voice("en-US", "English"), voice("hi-IN", "Hindi local", true), voice("hi-IN", "Hindi online")];

    expect(selectOptimalVoice(voices, "hi")?.name).toBe("Hindi online");
    expect(selectOptimalVoice(voices, "kn")).toBeNull(); // captions only: never Kannada in an English voice
    expect(selectOptimalVoice(voices)?.name).toBe("English");
  });

  it("puts the translated title and step texts on the workflow", () => {
    const out = applyTranslation(giteaWorkflowFixture, translation("ready"));

    expect(out.title).toBe("Ein Repository erstellen");
    expect(out.steps[0].instruction_text).toBe(`DE: ${giteaWorkflowFixture.steps[0].instruction_text}`);
    expect(out.steps.map((s) => s.seq)).toEqual(giteaWorkflowFixture.steps.map((s) => s.seq));
  });

  function renderTutorial(client: MockApiClient) {
    vi.spyOn(api, "getApiClient").mockReturnValue(client);
    render(<WorkflowTutorial workflowId={giteaWorkflowFixture.id} pollMs={1} />);
  }

  it("switches the tutorial to another language once it is translated", async () => {
    const client = new MockApiClient();
    const get = vi
      .spyOn(client, "getTranslation")
      .mockResolvedValueOnce(translation("translating"))
      .mockResolvedValueOnce(translation("ready", true));
    renderTutorial(client);

    fireEvent.change(await screen.findByTestId("tutorial-language-select"), { target: { value: "de" } });

    expect((await screen.findAllByText("Ein Repository erstellen")).length).toBeGreaterThan(0);
    expect(get).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("tutorial-language-status")).toHaveTextContent("still in English");
    expect(screen.getByTestId("tutorial-language-select")).toHaveValue("de");
  });

  it("stays in English when the translation fails", async () => {
    const client = new MockApiClient();
    vi.spyOn(client, "getTranslation").mockResolvedValue({ ...translation("failed"), error: "busy" });
    renderTutorial(client);

    fireEvent.change(await screen.findByTestId("tutorial-language-select"), { target: { value: "de" } });

    await waitFor(() => expect(screen.getByTestId("tutorial-language-status")).toHaveTextContent("couldn't be translated"));
    expect(screen.getByTestId("tutorial-language-select")).toHaveValue("en");
  });

  it("exports in the chosen language and says when it is captions only", async () => {
    const client = new MockApiClient();
    const create = vi.spyOn(client, "createExport");
    vi.spyOn(api, "getApiClient").mockReturnValue(client);
    render(<ExportVideoModal isOpen onClose={vi.fn()} workflowId="wf-1" initialLanguage="de" />);

    expect(screen.getByTestId("export-language-select")).toHaveValue("de");
    fireEvent.change(screen.getByTestId("export-language-select"), { target: { value: "hi" } });
    expect(screen.getByTestId("export-captions-only")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("start-export-btn"));

    await waitFor(() => expect(create).toHaveBeenCalledWith("wf-1", "landscape", "hi"));
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { TakeoverInput } from "@krama/contracts-ts";

import { TakeoverViewer } from "@/components/execution/takeover-viewer";
import { HttpApiClient, MockApiClient, MockScreen, type ScreenConnection, type TakeoverServerMessage } from "@/lib/api";

/** A screen whose server side the test drives. */
class ScriptedScreen implements ScreenConnection {
  readonly sent: TakeoverInput[] = [];
  frame: (url: string) => void = () => {};
  message: (m: TakeoverServerMessage) => void = () => {};
  closed: (code: number) => void = () => {};
  closedByClient = false;
  onFrame(l: (url: string) => void) {
    this.frame = l;
  }
  onMessage(l: (m: TakeoverServerMessage) => void) {
    this.message = l;
  }
  onClose(l: (code: number) => void) {
    this.closed = l;
  }
  send(input: TakeoverInput) {
    this.sent.push(input);
  }
  close() {
    this.closedByClient = true;
  }
}

function setup() {
  const client = new MockApiClient();
  const scripted = new ScriptedScreen();
  vi.spyOn(client, "openScreen").mockReturnValue(scripted);
  const handBack = vi.spyOn(client, "handBack").mockResolvedValue({ id: "run-1", status: "running" } as never);
  const onEnded = vi.fn();
  const view = render(<TakeoverViewer runId="run-1" stepSeq={3} client={client} onEnded={onEnded} />);
  return { client, scripted, handBack, onEnded, view };
}

describe("TakeoverViewer (#411)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("keeps one screen while the page re-renders, and ignores a screen it already closed", () => {
    // The run page re-rendered every second with a new client: the viewer reconnected each time until the
    // takeover ended (#431 gate).
    const { client, scripted, onEnded, view } = setup();
    view.rerender(<TakeoverViewer runId="run-1" stepSeq={3} client={new MockApiClient()} onEnded={onEnded} />);
    view.rerender(<TakeoverViewer runId="run-1" stepSeq={3} client={new MockApiClient()} onEnded={onEnded} />);
    expect(client.openScreen).toHaveBeenCalledTimes(1);
    expect(scripted.closedByClient).toBe(false);

    view.unmount();
    act(() => scripted.closed?.(1000)); // the closed socket's late close event
    expect(onEnded).not.toHaveBeenCalled();
  });

  it("shows the live frame and sends mouse input in page coordinates", () => {
    const { scripted } = setup();
    act(() => scripted.frame("blob:frame-1"));
    expect(screen.getByTestId("takeover-frame")).toHaveAttribute("src", "blob:frame-1");

    const surface = screen.getByTestId("takeover-surface");
    vi.spyOn(surface, "getBoundingClientRect").mockReturnValue({
      left: 10, top: 20, width: 640, height: 400, right: 650, bottom: 420, x: 10, y: 20, toJSON: () => ({}),
    } as DOMRect);
    fireEvent.mouseDown(surface, { clientX: 330, clientY: 220, button: 0, detail: 1 });
    fireEvent.mouseUp(surface, { clientX: 330, clientY: 220, button: 0, detail: 1 });

    expect(scripted.sent[0]).toEqual({ type: "mouse", event: "down", x: 640, y: 400, button: "left", click_count: 1 });
    expect(scripted.sent[1]).toMatchObject({ type: "mouse", event: "up", x: 640, y: 400 });
  });

  it("sends keys and pasted text", () => {
    const { scripted } = setup();
    const surface = screen.getByTestId("takeover-surface");

    fireEvent.keyDown(surface, { key: "Enter", code: "Enter" });
    fireEvent.keyUp(surface, { key: "Enter", code: "Enter" });
    fireEvent.paste(surface, { clipboardData: { getData: () => "pasted ✓" } });

    expect(scripted.sent).toEqual([
      { type: "key", event: "down", key: "Enter", code: "Enter", modifiers: { alt: false, ctrl: false, meta: false, shift: false } },
      { type: "key", event: "up", key: "Enter", code: "Enter", modifiers: { alt: false, ctrl: false, meta: false, shift: false } },
      { type: "text", text: "pasted ✓" },
    ]);
  });

  it("hands back with what the owner did", async () => {
    const { handBack, onEnded } = setup();

    fireEvent.click(screen.getByTestId("takeover-done-btn"));
    fireEvent.click(screen.getByTestId("handback-step"));

    await waitFor(() => expect(onEnded).toHaveBeenCalled());
    expect(handBack).toHaveBeenCalledWith("run-1", 3, "step");
  });

  it("shows blocked notices and the end of an idle takeover", () => {
    const { scripted } = setup();

    act(() => scripted.message({ type: "blocked", message: "Krama only opens pages on example.test here." }));
    expect(screen.getByTestId("takeover-notice")).toHaveTextContent("only opens pages");
    act(() => scripted.message({ type: "ended", reason: "idle" }));
    expect(screen.getByTestId("takeover-ended")).toHaveTextContent("5 minutes without input");
  });

  it("explains a refused connection", () => {
    const { scripted } = setup();

    act(() => scripted.closed(4409));

    expect(screen.getByTestId("takeover-ended")).toHaveTextContent("Someone else is already controlling");
  });

  it("closes the screen when it unmounts", () => {
    const { scripted, view } = setup();
    view.unmount();
    expect(scripted.closedByClient).toBe(true);
  });
});

describe("takeover in the API clients", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("calls the takeover routes and opens the screen WebSocket", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ id: "r", status: "paused" })));
    vi.stubGlobal("fetch", fetchMock);
    const sockets: string[] = [];
    class FakeSocket {
      binaryType = "";
      readyState = 0;
      constructor(url: string) {
        sockets.push(url);
      }
      addEventListener() {}
      send() {}
      close() {}
    }
    vi.stubGlobal("WebSocket", FakeSocket);
    const client = new HttpApiClient("http://127.0.0.1:8000/api/v1");

    await client.startTakeover("r 1");
    await client.handBack("r 1", 3, "barrier");
    client.openScreen("r 1");

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/v1/runs/r%201/takeover");
    expect(fetchMock.mock.calls[1][0]).toBe("http://127.0.0.1:8000/api/v1/runs/r%201/handback");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ step_seq: 3, done: "barrier" });
    expect(sockets).toEqual(["ws://127.0.0.1:8000/api/v1/runs/r%201/screen"]);
  });

  it("mock mode serves a fixture frame and records input", async () => {
    const mock = new MockScreen("/screenshots/step-1.png");
    const frames: string[] = [];
    mock.onFrame((url) => frames.push(url));
    mock.send({ type: "text", text: "x" });
    await waitFor(() => expect(frames).toEqual(["/screenshots/step-1.png"]));
    expect(mock.sent).toEqual([{ type: "text", text: "x" }]);
  });
});

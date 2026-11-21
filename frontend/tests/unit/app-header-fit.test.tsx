import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { AppHeader } from "@/components/app-shell/AppHeader";
import { LanguagePicker } from "@/components/app-shell/LanguagePicker";
import { MockApiClient } from "@/lib/api";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn(), back: vi.fn(), refresh }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// jsdom has no layout: the test sets the nav's widths and fires the resize observer by hand.
let resize: (() => void) | null = null;
class FakeResizeObserver {
  constructor(cb: () => void) {
    resize = cb;
  }
  observe() {}
  disconnect() {}
}

function widths(el: HTMLElement, scroll: number, client: number) {
  Object.defineProperty(el, "scrollWidth", { configurable: true, value: scroll });
  Object.defineProperty(el, "clientWidth", { configurable: true, value: client });
}

describe("the header fits any language (#423)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    refresh.mockReset();
    document.cookie = "KRAMA_LOCALE=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("shows only icons for the other tabs while the labels don't fit, and the labels again once they do", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    render(<AppHeader client={new MockApiClient()} />);
    const nav = screen.getByRole("navigation");

    widths(nav, 900, 600); // long labels (e.g. Kannada) overflow
    act(() => resize?.());
    expect(nav).toHaveAttribute("data-compact", "true");
    const tutorials = screen.getByRole("link", { name: /tutorials/i });
    expect(tutorials).toHaveAttribute("title"); // the name stays as a tooltip and for screen readers
    expect(screen.getByRole("link", { current: "page" })).not.toHaveAttribute("title"); // active keeps its label

    widths(nav, 600, 950); // the window grew past the full width
    act(() => resize?.());
    expect(nav).not.toHaveAttribute("data-compact");
  });

  it("picks a language from a small menu and saves it for the next request", () => {
    render(<LanguagePicker />);
    const button = screen.getByTestId("language-picker");
    expect(button).toHaveTextContent("EN");

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByTestId("language-option-kn"));

    expect(document.cookie).toContain("KRAMA_LOCALE=kn");
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("closes the menu on Escape without changing anything", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByTestId("language-picker"));
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("menu")).toBeNull();
    expect(refresh).not.toHaveBeenCalled();
  });
});

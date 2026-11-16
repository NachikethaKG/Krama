import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "@/components/ui";
import { THEME_STORAGE_KEY } from "@/lib/theme";

function resetTheme() {
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.classList.add("dark");
  localStorage.clear();
}

describe("ThemeToggle", () => {
  afterEach(resetTheme);

  it("starts dark and offers the light theme", () => {
    resetTheme();
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toHaveAttribute("data-theme-current", "dark");
  });

  it("switches to light, drops the dark class and remembers the choice", async () => {
    resetTheme();
    render(<ThemeToggle />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    });
    const root = document.documentElement;
    expect(root.getAttribute("data-theme")).toBe("light");
    expect(root.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(await screen.findByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
  });

  it("keeps several toggles on one page in sync", async () => {
    resetTheme();
    render(
      <>
        <ThemeToggle />
        <ThemeToggle />
      </>,
    );
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Switch to light theme" })[0]);
    });
    expect(await screen.findAllByRole("button", { name: "Switch to dark theme" })).toHaveLength(2);
  });
});

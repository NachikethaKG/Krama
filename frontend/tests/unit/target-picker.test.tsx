import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  GITEA_DEFAULT_URL,
  GITHUB_DEFAULT_URL,
  TargetPicker,
  validateTargetUrl,
} from "@/components/target-picker";

describe("validateTargetUrl", () => {
  it("validates empty or whitespace string", () => {
    expect(validateTargetUrl("").valid).toBe(false);
    expect(validateTargetUrl("   ").valid).toBe(false);
    expect(validateTargetUrl("").error).toContain("required");
  });

  it("rejects non-http(s) protocols like ftp://", () => {
    const res = validateTargetUrl("ftp://files.example.com/repo");
    expect(res.valid).toBe(false);
    expect(res.error).toMatch(/must use http:\/\/ or https:\/\//i);
  });

  it("rejects plain text strings without protocol", () => {
    const res = validateTargetUrl("invalid-endpoint-without-scheme");
    expect(res.valid).toBe(false);
    expect(res.error).toMatch(/please enter a valid url/i);
  });

  it("accepts valid http and https URLs", () => {
    expect(validateTargetUrl("http://localhost:3000").valid).toBe(true);
    expect(validateTargetUrl("https://github.com").valid).toBe(true);
    expect(validateTargetUrl("https://git.internal.corp:8443").valid).toBe(true);
  });
});

describe("TargetPicker component", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders all 3 target environment options", () => {
    render(<TargetPicker />);

    expect(screen.getByTestId("target-option-gitea")).toBeInTheDocument();
    expect(screen.getByTestId("target-option-github")).toBeInTheDocument();
    expect(screen.getByTestId("target-option-custom")).toBeInTheDocument();
  });

  it("defaults to Gitea option and keeps custom input hidden", () => {
    render(<TargetPicker />);

    const giteaBtn = screen.getByTestId("target-option-gitea");
    expect(giteaBtn).toHaveAttribute("aria-checked", "true");

    const customSection = screen.getByTestId("custom-target-section");
    expect(customSection).toHaveClass("hidden");
  });

  it("unhides custom target URL input when Custom Target is selected", () => {
    render(<TargetPicker />);

    const customBtn = screen.getByTestId("target-option-custom");
    fireEvent.click(customBtn);

    expect(customBtn).toHaveAttribute("aria-checked", "true");
    const customSection = screen.getByTestId("custom-target-section");
    expect(customSection).not.toHaveClass("hidden");

    const customInput = screen.getByTestId("custom-target-url-input");
    expect(customInput).toBeVisible();
  });

  it("shows validation error for malformed custom URL and clears error on valid URL", () => {
    render(<TargetPicker />);

    fireEvent.click(screen.getByTestId("target-option-custom"));
    const customInput = screen.getByTestId("custom-target-url-input");

    // Malformed protocol
    fireEvent.change(customInput, { target: { value: "ftp://wrong.protocol" } });
    expect(screen.getByTestId("target-url-error")).toHaveTextContent(
      /must use http:\/\/ or https:\/\//i,
    );

    // Plain text without scheme
    fireEvent.change(customInput, { target: { value: "my-plain-url" } });
    expect(screen.getByTestId("target-url-error")).toHaveTextContent(
      /please enter a valid url/i,
    );

    // Valid HTTPS URL
    fireEvent.change(customInput, { target: { value: "https://git.company.corp" } });
    expect(screen.queryByTestId("target-url-error")).toBeNull();
  });

  it("calls onChange callback when switching targets and validating URLs", () => {
    const onChange = vi.fn();
    render(<TargetPicker onChange={onChange} />);

    // Click GitHub
    fireEvent.click(screen.getByTestId("target-option-github"));
    expect(onChange).toHaveBeenCalledWith(
      { type: "github", url: GITHUB_DEFAULT_URL },
      true,
    );

    // Click Gitea
    fireEvent.click(screen.getByTestId("target-option-gitea"));
    expect(onChange).toHaveBeenCalledWith(
      { type: "gitea", url: GITEA_DEFAULT_URL },
      true,
    );

    // Click Custom
    fireEvent.click(screen.getByTestId("target-option-custom"));
    expect(onChange).toHaveBeenCalledWith(
      { type: "custom", url: "" },
      false,
    );

    // Type valid custom URL
    const customInput = screen.getByTestId("custom-target-url-input");
    fireEvent.change(customInput, { target: { value: "https://my-gitea.local" } });
    expect(onChange).toHaveBeenCalledWith(
      { type: "custom", url: "https://my-gitea.local" },
      true,
    );
  });

  it("persists selection to localStorage", () => {
    render(<TargetPicker />);

    fireEvent.click(screen.getByTestId("target-option-github"));

    const stored = localStorage.getItem("krama:target_config");
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed.type).toBe("github");
    expect(parsed.url).toBe(GITHUB_DEFAULT_URL);
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunPagination } from "@/components/runs/RunPagination";

function renderPagination(overrides: Partial<React.ComponentProps<typeof RunPagination>> = {}) {
  const props = {
    page: 1,
    pageSize: 5,
    itemCount: 5,
    hasPrevious: false,
    hasNext: true,
    onPrevious: vi.fn(),
    onNext: vi.fn(),
    ...overrides,
  };
  render(<RunPagination {...props} />);
  return props;
}

describe("RunPagination (cursor based)", () => {
  it("shows the range of the current page without inventing a total", () => {
    renderPagination({ page: 2, itemCount: 3, hasPrevious: true, hasNext: false });
    expect(screen.getByTestId("pagination-info")).toHaveTextContent("Showing 6 to 8 (Page 2, oldest runs)");
    expect(screen.getByTestId("current-page-num")).toHaveTextContent("2");
  });

  it("follows next_cursor with Older and pops back with Newer", () => {
    const props = renderPagination({ page: 2, hasPrevious: true, hasNext: true });
    fireEvent.click(screen.getByTestId("pagination-next"));
    fireEvent.click(screen.getByTestId("pagination-prev"));
    expect(props.onNext).toHaveBeenCalledTimes(1);
    expect(props.onPrevious).toHaveBeenCalledTimes(1);
  });

  it("disables Newer on the first page and Older when there is no next cursor", () => {
    renderPagination({ hasPrevious: false, hasNext: false });
    expect(screen.getByTestId("pagination-prev")).toBeDisabled();
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });

  it("disables both buttons while loading", () => {
    renderPagination({ page: 2, hasPrevious: true, hasNext: true, disabled: true });
    expect(screen.getByTestId("pagination-prev")).toBeDisabled();
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });

  it("handles an empty page", () => {
    renderPagination({ itemCount: 0, hasNext: false });
    expect(screen.getByTestId("pagination-info")).toHaveTextContent("No runs to display");
  });
});

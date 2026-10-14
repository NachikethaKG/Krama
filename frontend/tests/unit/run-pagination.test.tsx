import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunPagination } from "@/components/runs/RunPagination";

describe("RunPagination", () => {
  it("renders page info correctly on page 1 of 3", () => {
    const handlePageChange = vi.fn();
    render(
      <RunPagination
        page={1}
        totalPages={3}
        total={12}
        pageSize={5}
        onPageChange={handlePageChange}
      />
    );

    expect(screen.getByTestId("pagination-info")).toHaveTextContent("Showing 1 to 5 of 12 runs (Page 1 of 3)");
    expect(screen.getByTestId("current-page-num")).toHaveTextContent("1");
    expect(screen.getByTestId("total-pages-num")).toHaveTextContent("3");
  });

  it("disables Previous button on first page and enables Next button", () => {
    const handlePageChange = vi.fn();
    render(
      <RunPagination
        page={1}
        totalPages={3}
        total={12}
        pageSize={5}
        onPageChange={handlePageChange}
      />
    );

    const prevButton = screen.getByTestId("pagination-prev");
    const nextButton = screen.getByTestId("pagination-next");

    expect(prevButton).toBeDisabled();
    expect(nextButton).toBeEnabled();

    fireEvent.click(nextButton);
    expect(handlePageChange).toHaveBeenCalledWith(2);
  });

  it("disables Next button on last page and enables Previous button", () => {
    const handlePageChange = vi.fn();
    render(
      <RunPagination
        page={3}
        totalPages={3}
        total={12}
        pageSize={5}
        onPageChange={handlePageChange}
      />
    );

    const prevButton = screen.getByTestId("pagination-prev");
    const nextButton = screen.getByTestId("pagination-next");

    expect(prevButton).toBeEnabled();
    expect(nextButton).toBeDisabled();

    fireEvent.click(prevButton);
    expect(handlePageChange).toHaveBeenCalledWith(2);
  });

  it("disables all navigation buttons when disabled prop is true", () => {
    const handlePageChange = vi.fn();
    render(
      <RunPagination
        page={2}
        totalPages={3}
        total={12}
        pageSize={5}
        onPageChange={handlePageChange}
        disabled={true}
      />
    );

    expect(screen.getByTestId("pagination-prev")).toBeDisabled();
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });

  it("handles empty total items cleanly", () => {
    const handlePageChange = vi.fn();
    render(
      <RunPagination
        page={1}
        totalPages={1}
        total={0}
        pageSize={5}
        onPageChange={handlePageChange}
      />
    );

    expect(screen.getByTestId("pagination-info")).toHaveTextContent("No runs to display");
    expect(screen.getByTestId("pagination-prev")).toBeDisabled();
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });
});

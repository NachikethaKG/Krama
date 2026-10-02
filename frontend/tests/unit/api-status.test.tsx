import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiStatus } from "@/components/api-status";
import type { ApiClient } from "@/lib/api";

describe("ApiStatus", () => {
  it("shows the version when the API is healthy", async () => {
    const client: ApiClient = { health: async () => ({ status: "ok", version: "1.2.3" }) };

    render(<ApiStatus client={client} />);

    expect(await screen.findByText("API ok (version 1.2.3)")).toBeInTheDocument();
  });

  it("shows an error when the API is unreachable", async () => {
    const client: ApiClient = {
      health: async () => {
        throw new Error("connection refused");
      },
    };

    render(<ApiStatus client={client} />);

    expect(await screen.findByText("API unreachable: connection refused")).toBeInTheDocument();
  });
});

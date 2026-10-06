import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiStatus } from "@/components/api-status";
import { type ApiClient, MockApiClient } from "@/lib/api";

describe("ApiStatus", () => {
  it("shows the version when the API is healthy", async () => {
    class HealthyClient extends MockApiClient {
      override async health() {
        return { status: "ok" as const, version: "1.2.3" };
      }
    }

    render(<ApiStatus client={new HealthyClient()} />);

    expect(await screen.findByText("API ok (version 1.2.3)")).toBeInTheDocument();
  });

  it("shows an error when the API is unreachable", async () => {
    class FailingClient extends MockApiClient {
      override async health(): Promise<never> {
        throw new Error("connection refused");
      }
    }

    render(<ApiStatus client={new FailingClient()} />);

    expect(await screen.findByText("API unreachable: connection refused")).toBeInTheDocument();
  });
});

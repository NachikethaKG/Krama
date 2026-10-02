import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient, HttpApiClient, MockApiClient } from "@/lib/api";

describe("createApiClient", () => {
  it("defaults to the mock client", () => {
    expect(createApiClient(undefined)).toBeInstanceOf(MockApiClient);
  });

  it("uses the http client in http mode", () => {
    expect(createApiClient("http", "http://api")).toBeInstanceOf(HttpApiClient);
  });
});

describe("HttpApiClient", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the health payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", version: "0.1.0" }))),
    );

    await expect(new HttpApiClient("http://api").health()).resolves.toEqual({ status: "ok", version: "0.1.0" });
    expect(fetch).toHaveBeenCalledWith("http://api/health");
  });

  it("throws on a non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("down", { status: 503 })));

    await expect(new HttpApiClient("http://api").health()).rejects.toThrow("503");
  });
});

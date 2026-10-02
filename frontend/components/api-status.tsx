"use client";

import { useEffect, useState } from "react";

import { type ApiClient, createApiClient } from "@/lib/api";

type Status = { state: "loading" } | { state: "ok"; version: string } | { state: "error"; message: string };

export function ApiStatus({ client }: { client?: ApiClient }) {
  const [status, setStatus] = useState<Status>({ state: "loading" });

  useEffect(() => {
    const api = client ?? createApiClient();
    api
      .health()
      .then((health) => setStatus({ state: "ok", version: health.version }))
      .catch((error: unknown) =>
        setStatus({ state: "error", message: error instanceof Error ? error.message : "unreachable" }),
      );
  }, [client]);

  if (status.state === "loading") return <p role="status">Checking API…</p>;
  if (status.state === "error") return <p role="status">API unreachable: {status.message}</p>;
  return <p role="status">API ok (version {status.version})</p>;
}

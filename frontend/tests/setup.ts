import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { afterEach, vi } from "vitest";

// UI text (#423): components read it with next-intl. Tests render them without the root layout's provider,
// so next-intl's hooks get the English messages here, formatted by next-intl itself.
const MESSAGES_DIR = path.resolve(__dirname, "../messages/en");
export const englishMessages: Record<string, unknown> = Object.fromEntries(
  readdirSync(MESSAGES_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => [f.replace(/\.json$/, ""), JSON.parse(readFileSync(path.join(MESSAGES_DIR, f), "utf-8"))]),
);

vi.mock("next-intl", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next-intl")>();
  return {
    ...actual,
    useLocale: () => "en",
    useTranslations: (namespace?: string) =>
      actual.createTranslator({ locale: "en", messages: englishMessages as never, namespace: namespace as never }),
  };
});

vi.mock("next-intl/server", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next-intl/server")>();
  const { createTranslator } = await import("next-intl");
  return {
    ...actual,
    getLocale: async () => "en",
    getTranslations: async (namespace?: string) =>
      createTranslator({ locale: "en", messages: englishMessages as never, namespace: namespace as never }),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(cleanup);

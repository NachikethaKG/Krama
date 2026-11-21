import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Single .env at the repo root, shared with the backend (see .env.example).
loadEnvConfig(path.resolve(process.cwd(), ".."));

const nextConfig: NextConfig = {
  // The dev server trusts only localhost by default: on 127.0.0.1 (our Windows dev URL) it refused its own
  // live-reload socket and the page never hydrated (dead buttons, login looping back) (#431 gate).
  allowedDevOrigins: ["127.0.0.1"],
  transpilePackages: ["@krama/tutorial-compiler"],
  webpack: (config) => {
    config.resolve = config.resolve || {};
    config.resolve.extensionAlias = {
      ".js": [".ts", ".tsx", ".js", ".jsx"],
      ".mjs": [".mts", ".mjs"],
    };
    return config;
  },
};

// UI languages (#423): next-intl reads the request's language and messages in i18n/request.ts.
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

export default withNextIntl(nextConfig);

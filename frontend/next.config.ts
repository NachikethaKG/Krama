import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Single .env at the repo root, shared with the backend (see .env.example).
loadEnvConfig(path.resolve(process.cwd(), ".."));

const nextConfig: NextConfig = {};

export default nextConfig;

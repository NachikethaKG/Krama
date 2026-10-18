import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default {
  root: __dirname,
  resolve: {
    alias: {
      "@krama/contracts-ts": path.resolve(__dirname, "../contracts-ts/src/index.ts"),
      "ajv": path.resolve(__dirname, "../../frontend/node_modules/ajv"),
      "ajv/dist/2020.js": path.resolve(__dirname, "../../frontend/node_modules/ajv/dist/2020.js"),
      "ajv-formats": path.resolve(__dirname, "../../frontend/node_modules/ajv-formats"),
    },
  },
  test: {
    pool: "threads",
    include: ["tests/**/*.test.ts"],
  },
};

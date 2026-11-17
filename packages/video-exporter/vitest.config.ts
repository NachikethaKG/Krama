import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default {
  root: __dirname,
  resolve: {
    alias: {
      "@krama/contracts-ts": path.resolve(__dirname, "../contracts-ts/src/index.ts"),
      "@krama/tutorial-compiler": path.resolve(__dirname, "../tutorial-compiler/src/index.ts"),
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    include: ["tests/**/*.test.{ts,tsx}"],
  },
};

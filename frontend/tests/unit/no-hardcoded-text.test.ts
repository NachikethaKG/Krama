import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

/**
 * #424: every user-facing word of the app comes from messages/<locale>/*.json, so it can be translated. This
 * fails on new hard-coded text: words between JSX tags, and the placeholder / aria-label / title / alt
 * attributes as string literals. Tutorial content isn't here: it comes from the API.
 */

const ROOT = path.resolve(__dirname, "../..");
const SCANNED = ["app", "components"];
const ATTRIBUTES = new Set(["placeholder", "aria-label", "title", "alt"]);

/** Words that are the same in every language (product and site names, symbols). */
const ALLOWED = new Set(["Krama", "GitHub", "Gitea", "MP4", "WebVTT", "README", "URL", "OK"]);

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return files(full);
    return full.endsWith(".tsx") ? [full] : [];
  });
}

function isWords(text: string): boolean {
  const words = text.match(/\p{L}{2,}/gu) ?? [];
  return words.some((w) => !ALLOWED.has(w));
}

function hardcoded(file: string): string[] {
  const source = ts.createSourceFile(file, readFileSync(file, "utf-8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && isWords(node.getText())) {
      found.push(node.getText().trim());
    }
    if (ts.isJsxAttribute(node) && ATTRIBUTES.has(node.name.getText()) && node.initializer) {
      const init = node.initializer;
      const literal = ts.isStringLiteral(init)
        ? init.text
        : ts.isJsxExpression(init) && init.expression && ts.isStringLiteral(init.expression)
          ? init.expression.text
          : null;
      if (literal && isWords(literal)) found.push(`${node.name.getText()}="${literal}"`);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

describe("UI text comes from the messages (#424)", () => {
  it("has no hard-coded words in app/ and components/", () => {
    const offenders = SCANNED.flatMap((dir) => files(path.join(ROOT, dir)))
      .map((file) => ({ file: path.relative(ROOT, file), text: hardcoded(file) }))
      .filter((f) => f.text.length > 0);

    expect(offenders, JSON.stringify(offenders, null, 1)).toEqual([]);
  });
});

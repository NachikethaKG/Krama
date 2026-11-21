import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { LOCALES, NAMESPACES } from "@/i18n/config";

/**
 * #425/#426: a translated message must be safe to swap in for the English one: only keys English has, and the
 * same {placeholders}, plural/select arguments and rich-text tags. A key it lacks falls back to English.
 */

const DIR = path.resolve(__dirname, "../../messages");
type Tree = { [key: string]: string | Tree };

function load(locale: string, ns: string): Tree {
  try {
    return JSON.parse(readFileSync(path.join(DIR, locale, `${ns}.json`), "utf-8")) as Tree;
  } catch {
    return {};
  }
}

function leaves(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [k, v] of Object.entries(tree)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") out.set(key, v);
    else for (const [kk, vv] of leaves(v, key)) out.set(kk, vv);
  }
  return out;
}

/** The ICU arguments and tags a message uses: {name}, {count, plural, ...}, <b>...</b>. */
function shape(message: string): string[] {
  const args = [...message.matchAll(/\{\s*([A-Za-z_][\w]*)\s*(?:,\s*(plural|select|selectordinal|number|date|time))?/g)].map(
    (m) => `${m[1]}:${m[2] ?? ""}`,
  );
  const tags = [...message.matchAll(/<\/?([A-Za-z][\w-]*)>/g)].map((m) => `<${m[1]}>`);
  return [...new Set([...args, ...tags])].sort();
}

describe("translated messages fit the English ones (#425, #426)", () => {
  it("every message file exists for every UI language", () => {
    for (const locale of LOCALES) {
      const files = readdirSync(path.join(DIR, locale));
      for (const ns of NAMESPACES) expect(files, `${locale}/${ns}.json`).toContain(`${ns}.json`);
    }
  });

  for (const locale of LOCALES.filter((l) => l !== "en")) {
    it(`${locale}: only English keys, with the same arguments and tags`, () => {
      const problems: string[] = [];
      for (const ns of NAMESPACES) {
        const english = leaves(load("en", ns));
        for (const [key, text] of leaves(load(locale, ns))) {
          const en = english.get(key);
          if (en === undefined) problems.push(`${ns}.${key}: not an English key`);
          else if (JSON.stringify(shape(en)) !== JSON.stringify(shape(text))) {
            problems.push(`${ns}.${key}: ${JSON.stringify(shape(text))} != ${JSON.stringify(shape(en))}`);
          }
        }
      }
      expect(problems).toEqual([]);
    });
  }
});

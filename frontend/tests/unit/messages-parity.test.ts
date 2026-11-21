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

/** The ICU arguments and tags a message uses: {name}, {count, plural, ...}, <b>...</b>. Branch text inside a
 * plural/select (`one {step}`) is not an argument: it is translated. */
function shape(message: string): string[] {
  const args = new Set<string>();
  const text = (i: number): number => {
    while (i < message.length && message[i] !== "}") i = message[i] === "{" ? argument(i + 1) : i + 1;
    return i;
  };
  const argument = (i: number): number => {
    const head = /^\s*([A-Za-z_]\w*)\s*(?:,\s*(\w+)\s*)?/.exec(message.slice(i));
    if (!head) return text(i) + 1;
    i += head[0].length;
    args.add(`${head[1]}:${head[2] ?? ""}`);
    if (message[i] !== ",") return i + 1; // `{name}` or `{name, number}`
    i += 1;
    while (i < message.length) {
      const branch = /^\s*([^\s{}]+)\s*\{/.exec(message.slice(i)); // `one {`, `=0 {`, `other {`
      if (!branch) break;
      i = text(i + branch[0].length) + 1;
    }
    const close = message.indexOf("}", i);
    return close < 0 ? message.length : close + 1;
  };
  text(0);
  const tags = [...message.matchAll(/<\/?([A-Za-z][\w-]*)>/g)].map((m) => `<${m[1]}>`);
  return [...new Set([...args, ...tags])].sort();
}

describe("translated messages fit the English ones (#425, #426)", () => {
  it("reads arguments and tags, not plural branch text", () => {
    expect(shape("{count, plural, one {step} other {steps}}")).toEqual(["count:plural"]);
    expect(shape("{count, plural, one {# चरण} other {# चरण}}")).toEqual(["count:plural"]);
    expect(shape("Run {name} now")).toEqual(["name:"]);
    expect(shape("{n, plural, =0 {none} one {# by {user}} other {# items}}")).toEqual(["n:plural", "user:"]);
    expect(shape("Hi <b>{name}</b>, {when, date}")).toEqual(["<b>", "name:", "when:date"]);
  });

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

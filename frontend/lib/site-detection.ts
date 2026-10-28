/**
 * Which website a task is about, read from the prompt (#318). Users write what they want ("Show me how to
 * create a GitHub repository"); they never pick a target URL. Only sites Krama has a signed-in session and
 * planner hints for are offered: GitHub today. The local Gitea test site is a developer option.
 */

export interface Site {
  id: "github" | "gitea";
  name: string;
  url: string;
  /** Words that name the site in a prompt. */
  keywords: string[];
}

export const GITHUB: Site = { id: "github", name: "GitHub", url: "https://github.com", keywords: ["github"] };

export const GITEA: Site = {
  id: "gitea",
  name: "Gitea (local test site)",
  url: process.env.NEXT_PUBLIC_GITEA_URL || "http://localhost:3001",
  keywords: ["gitea"],
};

/** The sites a user can choose; Gitea only with NEXT_PUBLIC_DEV_TARGETS=1 (benchmarks and local testing). */
export function supportedSites(devTargets = process.env.NEXT_PUBLIC_DEV_TARGETS === "1"): Site[] {
  return devTargets ? [GITHUB, GITEA] : [GITHUB];
}

export type SiteDetection =
  | { kind: "found"; site: Site }
  | { kind: "none" }
  | { kind: "unsupported"; name: string }
  | { kind: "several"; sites: Site[] };

const URL_RE = /\bhttps?:\/\/([a-z0-9.-]+)(?::\d+)?/gi;
const DOMAIN_RE = /\b((?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|app|ai|co))\b/gi;

function hostOf(url: string): string {
  try {
    return new URL(url).host.toLowerCase();
  } catch {
    return "";
  }
}

/** The site the prompt is about. A URL or domain wins over a site name; an unknown domain is unsupported. */
export function detectSite(prompt: string, sites: Site[] = supportedSites()): SiteDetection {
  const text = prompt.toLowerCase();
  const hosts = [...text.matchAll(URL_RE)].map((m) => m[1]).concat([...text.matchAll(DOMAIN_RE)].map((m) => m[1]));
  for (const host of hosts) {
    const bare = host.replace(/^www\./, "");
    const site = sites.find((s) => hostOf(s.url).replace(/^www\./, "") === bare);
    if (site) return { kind: "found", site };
    if (!sites.some((s) => s.keywords.some((k) => bare.includes(k)))) return { kind: "unsupported", name: bare };
  }
  const named = sites.filter((s) => s.keywords.some((k) => new RegExp(`\\b${k}\\b`).test(text)));
  if (named.length === 1) return { kind: "found", site: named[0] };
  if (named.length > 1) return { kind: "several", sites: named };
  return { kind: "none" };
}

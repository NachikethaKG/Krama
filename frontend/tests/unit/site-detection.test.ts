import { describe, expect, it } from "vitest";
import { detectSite, GITEA, GITHUB, supportedSites } from "@/lib/site-detection";

describe("detectSite (#318)", () => {
  const users = [GITHUB];
  const devs = [GITHUB, GITEA];

  it("finds GitHub by name, in any case", () => {
    expect(detectSite("Show me how to create a GitHub repository", users)).toEqual({ kind: "found", site: GITHUB });
    expect(detectSite("create a label on github", users)).toEqual({ kind: "found", site: GITHUB });
  });

  it("finds GitHub by URL or domain", () => {
    expect(detectSite("open https://github.com/krama-bench and add a label", users)).toMatchObject({ site: GITHUB });
    expect(detectSite("on www.github.com make a branch", users)).toMatchObject({ site: GITHUB });
  });

  it("asks when no site is named", () => {
    expect(detectSite("Create a repository named demo", users)).toEqual({ kind: "none" });
  });

  it("says when the site isn't supported", () => {
    expect(detectSite("create a project on gitlab.com", users)).toEqual({ kind: "unsupported", name: "gitlab.com" });
    expect(detectSite("go to https://example.org/settings", users)).toEqual({ kind: "unsupported", name: "example.org" });
  });

  it("doesn't match a name inside another word", () => {
    expect(detectSite("my notgithubby notes", users)).toEqual({ kind: "none" });
  });

  it("offers the local Gitea test site only to developers", () => {
    expect(detectSite("create a repository in gitea", users)).toEqual({ kind: "none" });
    expect(detectSite("create a repository in gitea", devs)).toEqual({ kind: "found", site: GITEA });
    expect(detectSite("compare github and gitea", devs)).toEqual({ kind: "several", sites: [GITHUB, GITEA] });
    expect(supportedSites(false)).toEqual([GITHUB]);
    expect(supportedSites(true)).toEqual([GITHUB, GITEA]);
  });
});

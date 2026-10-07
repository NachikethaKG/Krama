# Playwright locators, expect and ARIA snapshots on Gitea

- **Phase:** 0
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** Playwright for Python: role-based locators (`get_by_role`, `get_by_label`), auto-waiting, `expect` assertions. What does `locator.aria_snapshot()` return, and how big is it on a Gitea page?

## Findings
- Tested with Playwright for Python **1.63.0**, headless Chromium, 1280×800, local Gitea **1.22.6** freshly reset (`just reset-gitea`). Script, raw snapshots and numbers: [`assets/phase-0-vishwas-aria-snapshots/`](assets/phase-0-vishwas-aria-snapshots/) [verified locally]
- **`aria_snapshot()` returns a YAML string** of the accessibility tree below the locator: `- role "name" [attributes]: text`, with children indented and links carrying `/url:` [verified locally]:

  ```yaml
  - main "demo - Dashboard":
    - heading "Repositories 0 New Repository" [level=4]:
      - link "New Repository":
        - /url: /repo/create
    - searchbox "Search repos..."
  ```

- **It includes form state**, so a verifier can check fills and checkboxes from the snapshot text alone [verified locally]:
  - `- textbox "Repository Name *": demo-repo` (current value after `fill`)
  - `- checkbox "Initialize Repository (Adds .gitignore, License and README)" [checked]`
- **Size** (tokens counted with Gemini `count_tokens`, model `gemini-3.8-flash`) [verified locally]:

  | Page | Scope | Chars | Tokens | Time |
  |---|---|---|---|---|
  | `/` dashboard | body | 1,114 | 378 | 68 ms |
  | `/` dashboard | main | 385 | 119 | 9 ms |
  | `/repo/create` | body | 2,829 | 778 | 50 ms |
  | `/repo/create` | main | 2,100 | 519 | 58 ms |
  | `/demo/demo-repo` | body | 3,493 | 1,384 | 29 ms |
  | `/demo/demo-repo` | main | 2,764 | 1,125 | 11 ms |

  Every Gitea page we need fits in ~1.4k tokens. A whole plan prompt with the dashboard snapshot was 701 prompt tokens (see the Gemini note). chars/4 underestimates tokens by ~30–60% on this YAML.
- **Gitea has no `<main>` tag.** The landmark is a `div role="main"`, so `page.locator("main")` timed out after 30 s; `page.get_by_role("main")` works. Always scope by role, not tag [verified locally]
- **Name matching:** `get_by_role("textbox", name="Repository Name")` (default substring, case-insensitive) finds 1; `exact=True` without the ` *` finds 0; `exact=True` with `"Repository Name *"` finds 1. `get_by_label("Repository Name")` also finds 1 [verified locally]. This matches the contract's `ElementRef` rule (substring match).
- **Auto-waiting:** actions wait for the element to be attached, visible, stable, enabled. A click on a missing button fails with `Locator.click: Timeout 2000ms exceeded.` after exactly the given timeout (2,003 ms) [verified locally]. The default timeout is 30 s, too long for an agent step; we must set our own.
- **`expect` assertions** retry until they pass or time out: `to_be_checked()` + `to_have_value("demo-repo")` passed in 22 ms; a wrong `to_have_url(...)` with `timeout=1000` raised `AssertionError` after 1,006 ms [verified locally]
- **`expect(locator).to_match_aria_snapshot(...)` does partial matching**: the template `- checkbox /Initialize Repository/ [checked]` (regex name) passed against the whole form [verified locally]. A possible verifier primitive for `visible` / `checked`.
- **Duplicate-name failure** shows up in the snapshot as `- paragraph: The repository name is already used.`: a plain paragraph, **not** `role="alert"` [verified locally]. A verifier looking only for alerts would miss it; the URL check (stays `/repo/create`) still catches it.
- **`locator.bounding_box()` returns viewport coordinates** (`{x: 519, y: 650, width: 153.5, height: 38}` for "Create Repository", page not scrolled) [verified: https://playwright.dev/python/docs/api/class-locator#locator-bounding-box]. The contract's `BoundingBox` says **page coordinates**, so the executor must add the scroll offset.

## Recommendation
Decisions (Vishwas, 2026-10-07):
- **Executor (#28):** locate by `get_by_role(role, name=name)` with the default substring match; set a short per-action timeout (proposal: 5 s) instead of Playwright's 30 s; never wait for `networkidle` (Phase F finding); convert `bounding_box()` to page coordinates (`+ window.scrollX/scrollY`) so we keep the contract as it is.
- **Verifier (#36):** check `url_matches` first (it catches the duplicate-name failure); check `visible` / `field_values` / `checked` against the ARIA snapshot text or with `expect` + short timeouts. Don't rely on `role="alert"` for errors.
- **Observer (#31, Nachiketha):** request, not a decision for us. Store the **full** `get_by_role("main")` snapshot in `ObservedState.aria_excerpt` (≤ ~1.2k tokens on Gitea), not a trimmed one, because the verifier needs the textbox values and `[checked]` flags. No change to `ports/` needed.

## Open questions
- Nachiketha: is the full `main` snapshot OK for `aria_excerpt`, or do you want a size cap (and if so, how do we keep form state)?
- Real GitHub pages (Phase 3) will be much larger than Gitea's; measure then.

## Links
- https://playwright.dev/python/docs/aria-snapshots
- https://playwright.dev/python/docs/locators
- https://playwright.dev/python/docs/test-assertions
- https://playwright.dev/python/docs/api/class-locator#locator-bounding-box

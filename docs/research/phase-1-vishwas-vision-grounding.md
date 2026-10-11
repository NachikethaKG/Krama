# Vision grounding with Gemini: boxes from screenshots

- **Phase:** 1
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **Vision grounding with Gemini:** how does Gemini return bounding boxes (normalized 0–1000, `[ymin, xmin, ymax, xmax]`)? How accurate is it on a Gitea screenshot? Turn a box into a Playwright click position.

## Findings
Experiments ran on 2026-10-11 against local Gitea 1.22.6 (logged in as `demo`), viewport 1280×800, google-genai 2.28.0 and Playwright 1.63. Gemini free tier, 9 requests in total. Scripts, screenshots and raw results: [`assets/phase-1-vishwas-vision-grounding/`](assets/phase-1-vishwas-vision-grounding/)

**Format** [verified: https://ai.google.dev/gemini-api/docs/image-understanding]
- Boxes are `box_2d = [ymin, xmin, ymax, xmax]`, "relative to image dimensions", scaled to **0–1000**. You "descale these coordinates based on your original image size". **y comes first.**
- The docs ask for it in the prompt ("The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000") together with a JSON schema. Our structured-output setup (`response_json_schema`, Phase 0) works unchanged: `{items: [{label, box_2d}]}` [verified locally].
- The docs suggest thinking level "minimal" for better results. **gemini-3.8-flash rejects it**: `400 INVALID_ARGUMENT: Thinking level MINIMAL is not supported for this model`. We used `low` for 3.x and `thinking_budget=0` for 2.5 [verified locally].

**Accuracy test.** We asked about 20 elements on 3 pages (dashboard, `/repo/create`, `/demo/demo-repo`): links, tabs, menus, a combobox, textboxes, checkboxes and icon-only buttons (Copy URL, New Pull Request). There was one request per page, listing all of that page's elements. Ground truth was Playwright's `bounding_box()` for the same role+name. A **hit** means the centre of Gemini's box falls inside the real element, i.e. a click there would land on it [verified locally: `ground.py`, `results-*.json`].

| Model | Click hits | Median centre error | Mean IoU | Latency per page (one request) |
|---|---|---|---|---|
| gemini-3.8-flash (thinking low) | **20/20** | **0.9 px** | 0.74 | 5.4 s, 8.0 s, **79.8 s** |
| gemini-3.5-flash (thinking low) | **20/20** | 1.7 px | 0.65 | 2.4 s, 3.7 s, 5.5 s |
| gemini-2.5-flash (thinking off) | 19/20 | 7.1 px | 0.34 | 4.3 s, 8.2 s, 10.8 s |

- The one miss: gemini-2.5-flash placed the **icon-only** "New Pull Request" button (a 38×30 px icon next to the branch picker) about 1,000 px away, at the top right. Icon-only controls named only by `aria-label` are the hard case.
- A low IoU with a good centre is fine for clicking. 2.5-flash draws loose boxes but still centres them.
- Latency varies: one 3.8 request took 80 s. A later 3.5 request failed with `503 UNAVAILABLE` ("high demand"). Vision calls need the same model fallback chain and 60 s timeout as planning (`app/llm/gemini.py`) [verified locally].

**Box → click position** [verified locally: `click_e2e.py`]
```python
ymin, xmin, ymax, xmax = box_2d                      # 0..1000, y first
vw, vh = page.viewport_size["width"], page.viewport_size["height"]   # CSS px, NOT the PNG size
x = (xmin + xmax) / 2 / 1000 * vw
y = (ymin + ymax) / 2 / 1000 * vh
await page.mouse.click(x, y)                         # viewport coordinates
```
- At `device_scale_factor=2` the screenshot is 2560×1600 px, but `page.mouse` uses CSS pixels (1280×800). Because the box is relative to the image, **scale by the CSS viewport size**. Scaling by the PNG size would click at (2449, 383), off-screen. End to end, gemini-3.8-flash's box for "New Repository" clicked at (1224, 192), and the page navigated to `/repo/create`.
- `page.mouse.click` takes **viewport** coordinates and the screenshot is the viewport, so they match. To store a contract `bbox` (page coordinates), add `window.scrollX/scrollY`, the same conversion as `ActionExecutor` (Phase 0).
- **A raw mouse click skips Playwright's actionability checks.** Before clicking, ask the page what is at that point: `document.elementFromPoint(x, y)`. Accept the click only if that element (or its closest interactive ancestor) has the planned role and name. This also protects against a box that lands on the wrong control.

**Cost.** One screenshot plus a short prompt costs a few hundred to ~1.5k input tokens [unverified: `usage_metadata` wasn't logged in this run]. More important is the request budget: the free tier allows 20 requests per day per model (Phase 0), so vision must be the **last** fallback, not a routine step.

## Recommendation
Decisions (Vishwas, 2026-10-11):
- **Vision is the last locator fallback** (role/name → text → CSS → vision), used only when the others matched no element or several ([phase-1-vishwas-agent-recovery](phase-1-vishwas-agent-recovery.md)). Ask about one element per request, with the planned role, name and instruction text.
- **Models:** the same chain as planning, 3.8-flash → 3.5-flash → 2.5-flash, through the existing `LLMProvider` (extend it with an image part). 3.x with thinking `low`, 2.5 with thinking off. 2.5 is the weakest on icon-only buttons, so treat a 2.5-only answer with the `elementFromPoint` check as mandatory, not optional.
- **Click at the box centre in CSS viewport pixels**, after an `elementFromPoint` check that the role and name match. Record verification `method: ["vision"]`, with lower confidence than an ARIA check (the threshold is agreed in #45).
- **Mask before sending:** the screenshot goes through Nachiketha's masking (blur sensitive fields) before any Gemini call (AGENTS.md §4). Never send a screenshot of a page with a visible password or token unmasked.

## Open questions
- Accuracy on denser pages (GitHub in Phase 3) and on non-English UIs is untested; re-run `ground.py` there.
- Is the 80 s outlier common for 3.8-flash? Log vision latency per model in the run log, and compare after the failure-injection benchmark.

## Links
- https://ai.google.dev/gemini-api/docs/image-understanding (object detection, box_2d format)
- https://playwright.dev/python/docs/api/class-mouse#mouse-click
- https://playwright.dev/python/docs/api/class-page#page-screenshot
- https://developer.mozilla.org/en-US/docs/Web/API/Document/elementFromPoint

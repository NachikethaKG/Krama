# Existing browser agents: browser-use and Stagehand vs our own layer

- **Phase:** 0
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** How do **browser-use** and **Stagehand** represent the page to the LLM (DOM, ARIA, screenshots) and its actions (click/fill/…)? Which runs from Python? Is either worth adopting, or do we copy ideas into our own thin layer? (This becomes ADR 0002.)

## Findings
Both were installed in throwaway venvs (not in `backend/`) and each ran one live task on local Gitea with `gemini-2.5-flash` on 2026-10-07. Scripts, logs and raw notes: [`assets/phase-0-vishwas-browser-agents/`](assets/phase-0-vishwas-browser-agents/)

**browser-use 0.13.11** (MIT, Python)
- **Footprint:** 106 packages, 227 MB venv. It pulls in SDKs for several LLM vendors, `google-api-python-client`, `mcp`, `reportlab`, `python-docx` and `pypdf`, and sends posthog telemetry unless `ANONYMIZED_TELEMETRY=false` [verified locally: package metadata, venv size]
- **No Playwright:** it drives Chrome over the DevTools protocol itself (`cdp-use`) [verified locally: dependencies]
- **Page representation:** it merges the DOM with Chrome's accessibility tree (`Accessibility.getFullAXTree`) into an **indexed list of interactive elements**, `[index]<tag attr=… />`. A star `*[` marks elements that are new since the last step, and a labelled screenshot is on by default (`use_vision=True`) [verified locally: `dom/service.py`, `system_prompt.md`]
- **Actions:** `click(index)`, `input`, `navigate`, `go_back`, `scroll`, `send_keys`, `select_dropdown`, `upload_file`, `switch`, `extract`, `search`, `wait`, `screenshot`, **`evaluate` (arbitrary JS)**, `done` [verified locally: `tools/service.py`]
- **Output:** JSON per step: `thinking`, `evaluation_previous_goal`, `memory`, `next_goal`, an optional `plan_update`, and a list of actions [verified locally]
- **Policy conflicts:** its system prompt says "CAPTCHAs are solved automatically" and "if blocked by login/403, consider alternative sites". Both contradict AGENTS.md §4 [verified locally: `system_prompt.md` lines 252, 263]
- **Live run:** **success** (`bu-test-1` created) [verified locally: [`browser-use-run-success.log`](assets/phase-0-vishwas-browser-agents/browser-use-run-success.log)]:
  - 39.5 s, 5 steps, 9 actions, 5 LLM calls
  - **34,975 tokens** (~7k per call, because of screenshots)
  - peak RAM 970 MB (Python + Chromium)
- **Browser launch hang:** 1 of 3 local launches hung past its 30 s watchdog [verified locally: [`browser-use-run-launch-hang.log`](assets/phase-0-vishwas-browser-agents/browser-use-run-launch-hang.log)]
- **429 handling:** retries 429/5xx up to 5 attempts with backoff of 1, 2, 4 and 8 s (+10% jitter) and ignores `RetryInfo.retryDelay`. With our 5-requests-per-minute free tier, a longer quota wait would use up the retries and fail [verified locally: `llm/google/chat.py` ~line 530]

**Stagehand 4.1.0** (MIT, PyPI `stagehand`)
- **Footprint:** 19 packages, 15 MB venv. The Python package is a thin JSON-RPC client. The logic is a **2 MB minified JavaScript Chrome extension** bundled in the package, so we couldn't realistically debug or patch it from Python [verified locally]
- **Runs fully locally:** `local_browser.launch(headless=True)` + `Stagehand.create()` + `goto` worked without a Browserbase key in 2.4 s; Browserbase is optional [verified locally]
- **Page representation:** its prompt calls it "a hybrid of the DOM and the accessibility tree", built from `getFullAXTree`. Elements get ids `[frame-backendNodeId]`; the LLM picks an id, which becomes an **absolute XPath** [verified locally: bundled extension source]
- **Primitives:** `act`, `observe`, `extract`, plus an agent mode. Options include `self_heal`, `cache` and `dom_settle_timeout_ms`. The model is a string (`gemini-2.5-flash` is listed) or a Python callback [verified locally]
- **Live run:** **success** (`sh-test-1` created) [verified locally: [`stagehand-run-success.log`](assets/phase-0-vishwas-browser-agents/stagehand-run-success.log)]:
  - `observe` 2.6 s, `act` type 2.8 s, `act` click 3.0 s
  - 3 LLM calls, **6,987 tokens** (~2.3k per call)
- **What `observe` returns:** `{selector: "xpath=/html[1]/body[1]/div[1]/div[1]/div[1]/div[1]/form[1]/div[1]/div[2]/input[1]", description: "Repository Name text input", method: "click"}`. An absolute XPath like this breaks easily when the page layout changes [verified locally]
- **Cache:** `DISABLED` on every call even with `cache=True`; its metadata calls it server-side caching, which suggests Browserbase's service [unverified]. Self-heal was not triggered [verified locally]

**Comparison**

| | Our own thin layer on Playwright | browser-use | Stagehand |
|---|---|---|---|
| Python support | native; Playwright 1.63 already in `uv.lock` | native, heavy (227 MB) | Python client, logic in a JS bundle |
| Page representation | ARIA snapshot YAML (~120–1,400 tokens on Gitea), our choice | indexed DOM+AX list + screenshot | DOM+AX hybrid, node ids → XPath |
| Reliability | deterministic per step: role locators, `expect`, our verifier | 1/1 live success; nondeterministic agent loop; 1 launch hang in 3; LLM judges its own success | 1/1 live success; absolute XPaths; cache disabled locally |
| CPU / cost per task | Chromium only; 1 planning call (~1.5k tokens) | ~970 MB RAM, ~35k tokens, 5 calls | ~7k tokens, 1 call per action |
| Lock-in | none | high: its own loop, prompts and policy | medium-high: opaque JS, Browserbase SDK |
| Fit with Plan → Approve → Execute + verify | direct | poor: plans and acts on its own | partial: `act` per step, no expected state |

## Recommendation
Proposed (pending Vishwas's decision; becomes **ADR 0002**, #30):
- **Build our own thin layer on raw Playwright.** Neither library fits the core flow: a plan approved by a human, executed step by step, each step checked mechanically by our verifier, and destructive actions paused by the policy layer. browser-use's prompt also contradicts our CAPTCHA and access rules. Both cost more tokens per task than one planning call plus deterministic execution.
- **Copy these ideas:**
  1. A compact **numbered list of interactive elements** from the ARIA snapshot, for re-grounding a step whose target didn't resolve (SeeAct's best method). Phase 1.
  2. browser-use's **"new since last step" marker**, to point the LLM at what changed.
  3. Stagehand's **observe / act split**: find candidates first, then act on one.
  4. A **cache of resolved targets** per step, with self-heal when a cached target stops matching (Phase 4, drift and healing). Store role+name, not absolute XPaths.
  5. Wait for the DOM to settle after an action, never `networkidle` (Phase F Gitea finding).
- **No architecture change:** `architecture.md` already says "Playwright Python" for the browser worker. The ADR records the choice and the reasons.

## Open questions
- Revisit if Phase 3 (real GitHub) shows our locator chain is much less robust than these libraries on large, changing pages.

## Links
- https://github.com/browser-use/browser-use
- https://github.com/browserbase/stagehand
- https://pypi.org/project/browser-use/
- https://pypi.org/project/stagehand/

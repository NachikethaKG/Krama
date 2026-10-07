# exp2: browser-use vs Stagehand (research #25 / ADR 0002), 2026-10-07
browser-use 0.13.11, MIT; venv 227 MB, 106 pkgs (anthropic, openai, groq, ollama, google-genai, google-api-python-client, mcp, posthog, reportlab, python-docx, pypdf...). No Playwright: drives Chrome via raw CDP (cdp-use) + bubus event bus.
 - Page repr: DOM+AX-tree merge (dom/service.py uses Accessibility.getFullAXTree) serialized as indexed XML `[index]<tag attr=.../>`, `*[` = new since last step; screenshot with bbox labels on by default (use_vision=True).
 - Output: JSON {thinking, evaluation_previous_goal, memory, next_goal, plan_update, action:[{navigate:{url}}, ...]} multiple actions per step.
 - Actions: search, navigate, go_back, wait, click(index), input, upload_file, switch, extract, scroll, send_keys, screenshot, select_dropdown, evaluate(JS), done.
 - System prompt: agent/system_prompts/system_prompt.md (copy: bu_system_prompt.md). Says "CAPTCHAs are solved automatically" (conflicts with our policy) and "If blocked by login/403, consider alternative sites".
 - Telemetry to eu.i.posthog.com unless ANONYMIZED_TELEMETRY=false.
 - Gemini: browser_use/llm/google/chat.py ChatGoogle via google-genai.
 - Launch: 1 of 3 local launches hung (>30s watchdog timeout, run1.log); retries 1.7s / 5.9s.
Stagehand (PyPI `stagehand`) 4.1.0, MIT; venv 15 MB, 19 pkgs (browserbase, pydantic, websockets, otel-api). Python is a thin JSON-RPC client; logic is a bundled 2 MB minified JS Chrome extension (_extension/service-worker.js) launched with local Chrome.
 - Runs locally: local_browser.launch(headless=True) + Stagehand.create() + goto worked with NO Browserbase key (smoke.log, 2.4s). Browserbase optional (api_key/api_url).
 - Page repr: "hybrid of the DOM and the accessibility tree" from Accessibility.getFullAXTree, element IDs [frame-backendNodeId]; LLM returns elementId -> xpath.
 - Primitives: act, observe, extract (+ agent); options self_heal, cache (CacheOptions), dom_settle_timeout_ms; model string (gemini-2.5-flash listed) or a Python LLM callback.
LIVE LLM RUNS PENDING A VALID GEMINI KEY: bu/run_bu.py (usage: .venv/Scripts/python.exe -I run_bu.py gemini-2.5-flash).
## Live runs (gemini-2.5-flash, key loaded from .env, 2026-10-07)
browser-use (bu/run2.log): SUCCESS, 39.5 s, 5 steps, 5 LLM requests (all 200, no 429), 9 actions, 34,975 tokens (~7k/call), peak RSS python+chromium 970 MB. Browser launched fine this time.
 429 handling (source, llm/google/chat.py ~L530): retries 429/5xx up to 5 attempts, exponential backoff 1,2,4,8 s + 10% jitter; ignores RetryInfo.retryDelay.
Stagehand (sh/run1.log): SUCCESS -> /demo/sh-test-1. observe 2.6 s, act type 2.8 s, act click 3.0 s; 3 LLM calls, 6,987 tokens total (~2.3k/call).
 observe output: [{selector: "xpath=/html[1]/body[1]/div[1]/.../form[1]/div[1]/div[2]/input[1]", description: "Repository Name text input", method: "click"}]
 cache: status DISABLED on every call even with cache=True ("server-side caching" = Browserbase API); self-heal not triggered.

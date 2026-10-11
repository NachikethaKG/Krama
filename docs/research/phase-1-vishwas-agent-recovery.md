# Agent recovery: retry, re-locate or replan a failed step

- **Phase:** 1
- **Researched by:** Vishwas (source reading by Claude Code, decisions by Vishwas)
- **Question(s):** **Agent recovery:** how do browser-use, Agent-E and SeeAct handle a failed step (retry the same action, re-locate the element, replan the rest)? What retry budget is sensible?

## Findings
Method: read the source at fixed commits (shallow clones, nothing run), plus the papers. Sources read on 2026-10-11:
- browser-use v0.13.11, commit `c75e847` (2026-10-07), abbreviated as BU = `github.com/browser-use/browser-use/blob/c75e847/browser_use`
- Agent-E commit `f218c3c` (2025-05-12), abbreviated as AE = `github.com/EmergenceAI/Agent-E/blob/f218c3c/ae`
- SeeAct commit `2434627` (2025-02-02), abbreviated as SA = `github.com/OSU-NLP-Group/SeeAct/blob/2434627`

| | browser-use | Agent-E | SeeAct |
|---|---|---|---|
| Detects failure by | the action's error result or an exception; the page is read again on every step | the skill's error string; a mutation observer reports what changed; the planner checks each step | a caught exception or no predicted element, counted as a "no-op" |
| Retries the same action? | no; the LLM decides again with the error in view | no; the navigator is told not to repeat a failed action | no; it **switches to a different action** (click → JS click → hover; type → select/click) |
| Re-locates the element? | yes, every step (fresh indexes); replay mode has a 5-level match cascade | yes ("Proceed by retrieving DOM again") | yes, re-ranks candidates every step |
| Replans? | a "REPLAN SUGGESTED" nudge after 3 failures in a row | the planner "MUST revise the plan" when one fails | only implicitly (it predicts the next action each step) |
| Budget defaults | `max_failures=5` (+1 final recovery call), `step_timeout=180s`, `llm_timeout=60s`, `max_steps=500`; replay: `max_retries=3`, backoff 5 s → 30 s | 50 planner rounds, 10 navigator rounds per subtask, 2 s element wait | repo configs: `max_continuous_no_op=2`, `max_op=20` (30 online); package defaults 5 / 50; 10 s action timeout |

**browser-use**
- It is a step-by-step loop, not plan-up-front. Each step reads the page again and the LLM picks new actions [verified: BU/agent/service.py#L1087-L1096].
- An unknown element index returns "Element index N not available - page may have changed" [verified: BU/tools/service.py#L716].
- Only errors count toward `consecutive_failures`; a success resets it to 0 [verified: BU/agent/service.py#L1232-L1242]. The agent stops at `max_failures + 1` (5 + 1) [verified: BU/agent/service.py#L2609-L2614, #L1582].
- After 3 failures in a row it injects "REPLAN SUGGESTED … Output a new `plan_update`" [verified: BU/agent/views.py#L79; BU/agent/service.py#L1464-L1477]. Loop nudges fire when similar actions repeat 5, 8 or 12 times [verified: BU/agent/views.py#L208-L232].
- When it runs several actions per step, it aborts the rest once the URL or focus changes [verified: BU/agent/service.py#L2730-L2828].
- **Closest to us: replaying a saved run (`rerun_history`).** It retries up to 3 times with exponential backoff from 5 s, capped at 30 s. It re-finds elements in this order: exact hash → stable hash (dynamic classes removed) → XPath → accessible name → unique attribute (id, name, aria-label). It can reopen a menu when the element is hidden inside one, and skips a retry that would repeat an action that already took effect [verified: BU/agent/service.py#L3103-L3110, #L3213-L3268, #L3536-L3640].
- The error reaches the next prompt cut to its first and last 100 characters [verified: BU/agent/message_manager/service.py].

**Agent-E**
- The planner/navigator split is its replan mechanism: the planner checks after each step and revises the plan on failure [verified: AE/core/prompts.py#L5-L35]. The navigator is told: "if something did not work after a few attempts, terminate" and report [verified: AE/core/prompts.py#L80-L81].
- It stops if the last 3 tool calls and responses are identical [verified: AE/utils/detect_llm_loops.py#L20-L44].
- Its click skill waits 2 s for the element and always clicks via JavaScript. The code comment says "Playwright click seems to fail more often than not" [verified: AE/core/skills/click_using_selector.py#L84-L130]. We should **not** copy this: a JS click skips Playwright's actionability checks, which are part of what makes our steps trustworthy.
- Paper: 73.2% on WebVoyager; about 52% of failed tasks were failures the agent itself noticed; ~25 LLM calls per task [verified: https://arxiv.org/html/2407.13032].

**SeeAct**
- It stops after `max_continuous_no_op=2` or `max_op=20` [verified: SA/src/config/auto_mode.toml#L14-L15; SA/src/seeact.py#L558-L561]. A failed action falls back to a different action type [verified: SA/src/seeact.py#L586-L612].
- Paper: **grounding is the bottleneck**. Step success with textual-choice grounding was 39.1% against 61.9% with perfect (oracle) grounding (Cross-Task). Online task success was 37.8% against 51.1% [verified: https://arxiv.org/html/2401.01614].

**Playwright (our first layer)**
- Every action waits for actionability (click: visible, stable, receives events, enabled; fill: visible, enabled, editable), then raises `TimeoutError` [verified: https://playwright.dev/docs/actionability].
- "Every time a locator is used for an action, an up-to-date DOM element is located", and locators are strict: they throw on more than one match [verified: https://playwright.dev/python/docs/locators]. Retrying the *same* locator at our level therefore adds almost nothing; Playwright already did that inside the timeout.

**Gap:** none of the three projects or papers publishes how often a retry or replan actually rescues a task [verified: absent from both papers].

**What makes Krama different.** All three loop "observe → LLM decides → act" with no fixed plan. Krama executes a **plan a human approved**. Any recovery that changes what happens (a different action, a new plan) silently overrides that approval. So our budget must be smaller, and changes must go back to the human.

## Recommendation
Decisions (Vishwas, 2026-10-11; the numbers are our synthesis, not from any source):
1. **Action timeout 5 s** (already `SessionConfig.action_timeout_ms=5000`). Playwright re-finds and waits inside it.
2. **Locator fallback chain, 1 try per strategy:** role+name → visible text → CSS selector → Gemini vision box ([phase-1-vishwas-vision-grounding](phase-1-vishwas-vision-grounding.md)). Each strategy must match **exactly one** element; zero or several means "try the next strategy". **Never change the action type** (no SeeAct-style click → hover), and never use JS clicks.
3. **Re-verify for 5 s** after an action, polling every 250 ms (already in `RunOptions`). If the action succeeded but verification failed, never repeat the action just to re-verify.
4. **Retry a whole step once, only if it is idempotent:** navigate, wait, fill, select. **Never re-click or re-press:** the first attempt may already have taken effect (a second "Create Repository" click could create a duplicate).
5. **Replan: at most 1 per step and 3 per run.** Replan only the remaining steps. Send the failure (expected vs observed) to the LLM as delimited data. **Changed steps need human re-approval** (`run.replanning` → `paused`).
6. **Pause for the human instead of retrying** when:
   - the step is destructive or policy-flagged;
   - there's a CAPTCHA, bot wall or login/2FA page;
   - a locator matches several elements at every strategy;
   - 2 steps in a row failed;
   - the replan budget is used up.
7. **Run timeout 10 minutes overall**, plus the existing 60 s per LLM request. Hitting it means `failed`.
8. `runs.retry_count` (already in the contract) counts step retries plus replans, so the UI can show how hard a run had to work.

## Open questions
- The failure-injection benchmark (Nachiketha, sprint 1.2) should report how often each recovery layer rescued a step. That would be the first real data, since no published project has any.
- Should a replan that only changes locators (same actions, same order) still need re-approval? Proposed: no, because the human approved *what* happens, not *how* an element is found. To confirm together in #45.

## Links
- https://github.com/browser-use/browser-use/blob/c75e847/browser_use/agent/service.py
- https://github.com/browser-use/browser-use/blob/c75e847/browser_use/agent/views.py
- https://github.com/browser-use/browser-use/blob/c75e847/browser_use/tools/service.py
- https://github.com/browser-use/browser-use/blob/c75e847/browser_use/agent/message_manager/service.py
- https://github.com/EmergenceAI/Agent-E/blob/f218c3c/ae/core/prompts.py
- https://github.com/EmergenceAI/Agent-E/blob/f218c3c/ae/core/autogen_wrapper.py
- https://github.com/EmergenceAI/Agent-E/blob/f218c3c/ae/utils/detect_llm_loops.py
- https://github.com/EmergenceAI/Agent-E/blob/f218c3c/ae/core/skills/click_using_selector.py
- https://github.com/OSU-NLP-Group/SeeAct/blob/2434627/src/seeact.py
- https://github.com/OSU-NLP-Group/SeeAct/blob/2434627/src/config/auto_mode.toml
- https://github.com/OSU-NLP-Group/SeeAct/blob/2434627/seeact_package/seeact/agent.py
- https://playwright.dev/docs/actionability
- https://playwright.dev/python/docs/locators
- https://arxiv.org/abs/2407.13032 (Agent-E)
- https://arxiv.org/abs/2401.01614 (SeeAct)

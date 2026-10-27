# Self-healing locators: scoring candidates, LLM re-grounding, and never healing onto the wrong element

- **Phase:** 4
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-26; decisions by Vishwas)
- **Question(s):** **Self-healing locators:** how does Healenium score candidate elements when a locator breaks (attribute similarity, position, text)? When is LLM re-grounding (screenshot + ARIA) better? How do you avoid "healing" onto the wrong element?

## Findings

Read from source: healenium-web 3.5.8 (commit `c1e4f83`, 2026-03-03) and its scoring library `tree-comparing` 0.4.14
(sources jar from Maven Central; the library isn't on GitHub). Checks ran against local Gitea 1.22.6 with Playwright
1.63.0 / Chromium 153. Script, raw results and console output:
[`assets/phase-4-vishwas-checks/`](assets/phase-4-vishwas-checks/) (`heal_scores.py`, `results-heal.json`, `output.txt`).

**How Healenium heals** [verified: healenium-web `SelfHealingEngine.java`, `HealingService.java`, `itemsWithAttributes.js`]
- Every time a locator **succeeds**, it saves the element's node path from `<html>` down to the element. Each node
  keeps `tag`, `id`, `classes`, every other attribute, its index among siblings, and `innerText`. The data goes to
  its own backend service (Postgres).
- When a locator **fails**, it parses the current page (`document.body.outerHTML`, jsoup), scores candidates against
  the saved path, takes the best ones at or above `score-cap`, and builds a new CSS selector (tag+id, tag+class, …,
  full path) that matches exactly one element. Defaults: `score-cap = .6`, `recovery-tries = 1`, `heal-enabled = true`
  [verified: `src/main/resources/application.conf`].
- License Apache 2.0 [verified: `pom.xml`]. There is also a paid `hlm-ai` service ("You must have a paid hlm-ai
  service") [verified: `RestClient.java`]. Playwright support runs through a separate proxy server
  (`ws://localhost:8095/hlm-playwright-proxy`) [verified: `healenium-example-playwright-python` README].

**Healenium's score** [verified: tree-comparing 0.4.14 `PathFinder`, `LCSPathDistance`, `HeuristicNodeDistance`]
1. **Path step:** it computes the longest common subsequence (LCS) between the saved path and the root-to-leaf path
   of every leaf in the new page. Two nodes count as equal when **tag and id** are equal. Candidates are the nodes of
   each leaf path from position `LCS-1` downward.
2. **Node step:** each candidate gets points, normalized by the 450 maximum:

   | Signal | Points | How |
   |---|---|---|
   | Path similarity (LCS / path height) | 100 | score is 0 if the path is longer than 5 and LCS/height < 0.7 |
   | Same tag | 100 | exact, case-insensitive |
   | id | 50 | Levenshtein similarity, 0 beyond 30 % edits |
   | classes | 40 | shared classes / all classes, plus Levenshtein credit for near-miss class names |
   | text (`innerText`) | **30** | Levenshtein similarity, 0 beyond 30 % edits |
   | other attributes | 30 | average Levenshtein similarity per attribute (0 beyond 75 %) |
   | index among siblings | **0** | position plays no part |

   So Healenium is **mostly structural**: tag + path give 200 of 450 points, text gives only 30, and position gives
   none. Ties are not handled: equal scores keep stream order, and there is **no margin check** between the first and
   second candidate.

**What it does on our pages.** We ported the scorer line by line to Python and compared it with a Krama-style score:
same ARIA role only, then 0.30 name similarity + 0.20 same container (`element_context`: dialog / section heading)
+ 0.20 same form (action URL + hidden `action` value) + 0.20 same stable attribute (`id` or `name=`) + 0.10 position.
The Krama score heals only if top ≥ 0.75 **and** top − second ≥ 0.15. "Truth" is the control that really is the
same one after the drift; it's tracked by object identity, so neither scorer can see it [verified locally].

| Scenario (Gitea) | Today's chain (`ActionExecutor`) | Healenium (cap 0.6) | Krama score + margin |
|---|---|---|---|
| "Create Repository" renamed "Make repo" | `target_not_found` | right, 0.91 vs 0.52 | right, 0.76 (only button) |
| same button restyled (class + id) | **finds it** (role) | right, 0.79 | right |
| same button moved into a new wrapper | **finds it** (role) | right, 1.0 | below threshold (no heal needed anyway) |
| renamed + restyled | `target_not_found` | right, 0.72 | right, 0.76 |
| button removed | `target_not_found` | no heal (0.55) | no heal |
| "Repository Name" label changed | `target_not_found` | right, 1.0 (same `id`) | right, 0.86 vs 0.56 |
| settings: description's "Update Settings" renamed "Save" | `ambiguous_target` | **WRONG: another "Update Settings", 1.0** | no heal (0.66) |
| settings: that button removed | `ambiguous_target` | **WRONG: another "Update Settings", 1.0** | no heal (0.56) |

What this shows:
1. **Our role+name chain already "heals" restyles and moves.** It doesn't depend on CSS, so class, id and position
   changes never break it. Healing is needed only when the **accessible name** changes, or the element is gone.
2. **Healenium's worst case is our common case.** Gitea's settings page has three structurally identical "Update
   Settings" buttons in different forms. Once the real one is renamed or removed, both others score a perfect 1.0
   and Healenium would heal onto one at full confidence. Same tag, same classes, same text, and an LCS path that
   matches because forms have no ids.
3. **Without a margin, our score fails the same way.** The first weighting (no form signal) put "Update Avatar" on
   top in both settings cases (0.76 and 0.78). Only the margin rule (0.11 and 0.12 < 0.15) stopped a wrong heal
   (`output.txt`). Form identity and stable attributes are what tell look-alikes apart. Neither scorer can do it on
   text alone.
4. **The case nothing deterministic solves** is "renamed, among look-alikes" (settings → "Save"). It's correctly
   *not* healed, so it goes to the LLM or to OUTDATED.
5. These numbers are from **10 scenarios on 2 pages**, and the weights were tuned on them. Treat the rule's *shape*
   (role gate + independent signals + margin + verify after) as the finding, not the exact weights.

**LLM re-grounding (screenshot + ARIA): when it's better**
- Today's `GeminiVisionLocator` only **picks among elements that already match** the planned role+name (`_pick_with_vision`),
  and the prompt says "never guess" and names the *old* name [verified: `app/agent/vision.py`, `executor.py`]. For
  healing that's the wrong question: on the settings page, asking for "Update Settings" can only point at one of the
  **wrong** remaining buttons, or say `found=false`.
- Where an LLM is genuinely better: a rename with no lexical overlap ("Update Settings" → "Save") where the *purpose*
  is still clear from the step text ("save the description") and the layout. Also icon-only controls, and a control
  moved into a menu or dialog. Deterministic scores have no notion of purpose. [unverified: we couldn't run the
  Gemini check today, see below]
- Phase 1 measured accuracy: gemini-3.8/3.5-flash hit 20/20 elements, but latency went up to 80 s, and the free tier
  is ~20 requests/day/model (`phase-1-vishwas-vision-grounding.md`).
- **Today's run is itself a finding:** all 3 vision calls failed. gemini-3.5-flash and 2.5-flash returned `429`
  (daily quota used up) and gemini-3.8-flash returned `503` ("high demand"). 15 failed attempts in total, counting a
  diagnostic call that ran twice by mistake [verified locally: `output.txt`]. Healing **must not depend on Gemini
  being available**: no answer has to end as OUTDATED / review, never as a retry loop.
- A heal prompt should differ from the locate prompt: give the step's purpose (`instruction_text`, `expected_state`),
  the old name as a hint ("may have been renamed"), the stored step **screenshot** with the old box drawn (we keep
  `screenshot_path` per step), and the **candidate list from the ARIA snapshot** as numbered options. Then the
  model picks an option ID instead of drawing a free box. [unverified: `LLMProvider.generate` takes one `image`
  today; two images need a small provider change.] All of it goes in as delimited untrusted data (AGENTS.md §4).

**Avoiding a heal onto the wrong element: what the code needs** [verified by reading `app/agent/`, `app/runs/`]
- Heal only after a **locator miss** (`target_not_found`, `ambiguous_target`), never after a state mismatch. #109
  exposes exactly that split (`phase-2-vishwas-reverify.md`).
- A candidate must have the **same role**, win by a **margin**, and agree on at least one structural anchor (same
  form or stable attribute). An LLM pick gets the same gate: the point must land on one of the gated candidates.
- **Policy runs again on the healed target.** The new name is what `policy/` classifies, so a heal onto
  "Delete…" pauses or refuses like any destructive action. Never auto-heal a high-risk step: reverify already refuses
  them (`check_replayable`).
- **Verify after, end to end:** the healed step's `expected_state` must verify. Then every later step must verify
  too, before a new version is saved. Any failure after a heal discards it: no partial versions.
- Since a click acts for real, healing runs from the workflow's reset starting state, like reverify. A wrong click
  then lands on throwaway data (Gitea reset, GitHub test org).

## Recommendation
1. **Don't adopt Healenium itself.** It heals CSS/XPath locators we don't use, it needs its own Java backend (plus
   a proxy for Playwright), and its structure-only score heals onto look-alikes. Take two ideas from it: **record a
   fingerprint when the step succeeds**, and **score candidates on several independent signals**.
2. **Store a small fingerprint per step** when a workflow is saved: `role`, `name`, `element_context`, form signature,
   `id` / `name=` attribute, `bbox`. It fits in the existing `workflow_steps.target` jsonb; the contract `Target`
   stays `{role, name, selector}`. **Decision for Vishwas:** is an extra internal key in `target` OK, or should it be
   a separate `fingerprint` column (schema change via #108)?
3. **Healing chain for #112**, after the normal chain misses:
   (a) deterministic candidate score with the margin rule. This decides the easy renames for free and offline.
   (b) only if (a) declines and the step isn't high risk, one Gemini call that chooses among the ARIA candidates.
   (c) policy check on the chosen target, act, verify the step, replay the rest, then save a new version (`source = heal`).
   (d) anything else → OUTDATED, with the candidates and scores in the drift details for the review queue.
4. **Fixtures for #112 tests:** the 10 scenarios in `heal_scores.py` (drift via `add_init_script`) are cheap,
   deterministic Gitea tests. The settings pair is the regression test for "never heal onto a look-alike".

No `architecture.md` change: "self-healing (Phase 4)" is already in `agent/`, and the locator chain gains one step
after the miss. If the fingerprint becomes its own column, that's a `database-schema.md` contract change, not an ADR.

## For the #107 call (together): auto-heal vs OUTDATED vs human review
A starting proposal to discuss, not a decision:
- **Auto-heal, publish right away:** deterministic heal with a margin, low/medium-risk step, whole workflow
  re-verified. The new version is marked `healed` so the UI can show a badge and the diff.
- **Auto-heal, held for review:** an LLM-chosen heal, or a heal that changed a step's name and its expected
  text. The new version is saved but not current until a human accepts it. (This needs a version status, see
  `phase-4-vishwas-workflow-versioning.md`.)
- **OUTDATED + review queue:** no candidate passes, Gemini unavailable or declines, the heal fails to verify, a
  high-risk step is involved, or the step after a heal fails (a changed flow, not a renamed control).
- **Who's notified:** the workflow's owner (`workflows.user_id`). How (UI badge only vs e-mail) is Nachiketha's
  review-queue question.

## Open questions
- Today's Gemini quota was used up, so the "LLM re-grounding beats deterministic scoring on settings → Save" claim
  is **[unverified]**. Re-run `heal_scores.py --vision` on a fresh quota day (3 requests).
- Margin 0.15 and threshold 0.75 come from 10 scenarios. Add GitHub pages (#89's tasks) to the fixture set before
  trusting them.
- Should a heal also refresh the instruction text? A renamed button makes "Click “Create Repository”" wrong. The
  text is code-written (ADR 0003), so regenerating it from the new name is free, but it's a definition change (→
  new version).
- #112's "Allowed paths" is only `backend/app/agent/**`, but saving a version touches `runs/` and `db/`. Widen the
  issue scope (both are Vishwas's areas).

## Links
- https://github.com/healenium/healenium-web (3.5.8, `c1e4f83`): `SelfHealingEngine.java`, `service/HealingService.java`, `src/main/resources/{application.conf,itemsWithAttributes.js}`, `client/RestClient.java`
- https://repo1.maven.org/maven2/com/epam/healenium/tree-comparing/0.4.14/ (sources jar: `PathFinder`, `LCSPathDistance`, `HeuristicNodeDistance`, `JsoupHTMLParser`)
- https://github.com/healenium/healenium-example-playwright-python (proxy setup)
- `backend/app/agent/executor.py`, `backend/app/agent/vision.py`, `backend/app/agent/context.py`, `backend/app/verifier/aria.py`, `backend/app/runs/reverify.py`
- `docs/research/phase-1-vishwas-vision-grounding.md`, `phase-1-vishwas-agent-recovery.md`, `phase-2-vishwas-reverify.md`

# Phase 1 Research Summary & Action Items

- **Phase:** 1 (Verified Workflow)
- **Sprint:** 1.1 · Plan → approve → execute (Phase 1 Research Spike)
- **Researched by:** Nachiketha
- **Target Issue:** #44

---

## 1. Executive Summary

This research note concludes the Phase 1 research spike for Nachiketha (#44), covering the core safety, policy, masking, detection, and frontend stream architecture required for Phase 1 ("Verified Workflow Engine").

### Completed Research Notes in this Spike:
1. [`docs/research/phase-1-nachiketha-prompt-injection.md`](phase-1-nachiketha-prompt-injection.md): Untrusted web content boundaries (`<untrusted_web_content>`), tag escaping, and structural state machine action validation.
2. [`docs/research/phase-1-nachiketha-bot-wall-detection.md`](phase-1-nachiketha-bot-wall-detection.md): Signatures for Cloudflare Turnstile, reCAPTCHA, hCaptcha, and auth-walls; stop-the-run enforcement.
3. [`docs/research/phase-1-nachiketha-masking-and-privacy.md`](phase-1-nachiketha-masking-and-privacy.md): rrweb masking configuration, Pillow Gaussian bbox blur for screenshots, regex for keys/tokens; omission of Presidio to conserve 16GB RAM budget.
4. [`docs/research/phase-1-nachiketha-destructive-actions.md`](phase-1-nachiketha-destructive-actions.md): Two-tier classification (keyword + entity/path validation) and Gitea destructive baseline actions.
5. [`docs/research/phase-1-nachiketha-frontend-sse-and-diff.md`](phase-1-nachiketha-frontend-sse-and-diff.md): SSE client reconnection using `Last-Event-ID` against `run_events` and side-by-side / split-slider screenshot diff UI.

---

## 2. Decisions Made

- **Prompt Injection Defense:** Strict XML delimitation `<untrusted_web_content>` with delimiter tag escaping. The execution engine enforces an allow-list of known actions and plan steps; no dedicated LLM pre-classifier will be used to protect the Gemini free-tier quota and keep latency low.
- **Bot-Wall & CAPTCHA Policy:** Fast Playwright locator detection (<10ms). Never attempt bypass or automated solving; pause execution immediately with `automation_restricted` state for human takeover.
- **Masking & Privacy:** Localized Pillow Gaussian blur (`radius=15`) over Playwright element bounding boxes for screenshots; targeted regex for API keys and tokens. Presidio is excluded due to memory (500MB–1GB) and CPU latency (150–400ms) constraints.
- **Destructive-Action Classification:** Two-tier detection (`action + entity + route`) to avoid false positives on benign UI elements (e.g., "Delete draft"). High-risk actions pause execution for human confirmation.
- **Frontend Live Execution Stream:** Custom React hook with `Last-Event-ID` tracking, paired with lightweight CSS/Tailwind side-by-side screenshot diff components.

---

## 3. Decisions Needing Vishwas / Team Alignment (#45)

1. **Destructive Action Confirmation Contract:** Confirm the exact schema for the pause event and confirmation payload on `POST /runs/{id}/confirm` (resume vs abort).
2. **Failure-Injection Benchmarks:** Define the standard test set of intentionally broken actions for Sprint 1.2 verifier accuracy measurement.
3. **Prompt Injection Test Page:** Finalize the mock injection page structure in Gitea/local HTML for Sprint 1.3 verification tests.

---

## 4. Sprint Implementation Roadmap

- **Sprint 1.1:**
  - Persist observer captures through the `ArtifactStore` port (`backend/app/observer/`).
  - Wire frontend plan editing, cancel controls, and pause/error banner states.
- **Sprint 1.2:**
  - Build failure-injection benchmark harness in `benchmarks/` to measure verifier recall.
  - Implement Expected vs Observed screenshot diff UI in frontend.
- **Sprint 1.3:**
  - Implement `backend/app/policy/`: bot-wall detector, PII regex + screenshot blur, and risk classifier.
  - Test agent resilience against the prompt-injection test page.
  - Add confirmation modal and "Automation restricted" screens in frontend.

---

Closes #44

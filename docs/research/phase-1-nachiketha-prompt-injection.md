# Prompt Injection & Indirect Injection Defense (OWASP LLM01)

- **Phase:** 1
- **Researched by:** Nachiketha
- **Question(s):** Prompt injection: OWASP Top 10 for LLM Applications, LLM01 (prompt injection), especially *indirect* injection through web content. What defenses work: data delimiting, separate classifier, allow-listed actions?

## Findings

- **OWASP LLM01 Threat Model:** Web content (DOM text, ARIA attributes, page text, form placeholders) is untrusted user input that can carry indirect prompt injection attacks (e.g., hidden instructions instructing the agent to delete data, navigate elsewhere, or exfiltrate tokens) [verified: OWASP LLM Applications LLM01, https://genai.owasp.org/llmrisk/llm01-prompt-injection/].
- **XML Data Delimitation:** Untrusted webpage content must be strictly enclosed within demarcated XML boundary tags such as `<untrusted_web_content>...</untrusted_web_content>` [verified: OWASP LLM Applications LLM01]. The LLM system prompt explicitly instructs the planner that content inside these tags represents passive perceptual data, never actionable instructions.
- **Delimiter Sanitization:** Web content can contain malicious closing tags (`</untrusted_web_content>`) to achieve tag breakout. All content placed inside boundaries must be sanitized by escaping or stripping nested delimiter tags prior to prompt construction [verified locally].
- **Separate Classifier Feasibility:** Running a dedicated pre-classifier LLM call to evaluate untrusted text before each step adds 300–800ms of latency per step and doubles request volume against the free-tier Gemini API quota (20 RPD ceiling). It was rejected for per-step runtime checks [verified locally].
- **Structural State Machine Defense:** The execution engine enforces an approved plan schema. The runtime state machine validates each step against strict Pydantic models and allow-listed browser actions (`click`, `fill`, `select`, `navigate`, `press`, `wait`), rendering arbitrary injection payloads harmless because unapproved actions are rejected at the executor boundary [verified: docs/architecture.md].

## Recommendation

Implement a two-tier structural defense:
1. Wrap all page context in sanitized XML boundary tags (`<untrusted_web_content>`).
2. Rely on strict plan-approval validation and action allow-listing in the execution state machine rather than an expensive per-step standalone injection classifier.
[No ADR required: conforms to product-code safety rules in AGENTS.md §4 and docs/architecture.md].

## Open questions

- How should the system handle adversarial text disguised as UI form field labels without confusing the planner? (To test in Sprint 1.3 prompt-injection test page).

## Links

- [OWASP Top 10 for LLM Applications - LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [Krama Architecture Blueprint](file:///c:/Git/Krama/docs/architecture.md)
- [Agent Guardrails](file:///c:/Git/Krama/docs/setup/agent-guardrails.md)

# Masking & Privacy (rrweb, Screenshots, and PII)

- **Phase:** 1
- **Researched by:** Nachiketha
- **Question(s):** Masking: rrweb privacy options (`maskAllInputs`, `maskTextClass`, `blockClass`, `maskInputFn`). How do you mask sensitive values in screenshots (blur the element's bbox before saving)? Regex patterns for tokens/keys vs Microsoft Presidio for PII (does it run fast enough on CPU?).

## Findings

- **rrweb Privacy Configuration:**
  - `maskAllInputs: true`: Masks all `<input>` elements into asterisks (`****`). Note: this can obscure benign tutorial fields (such as repository names), so granular masking is preferred [verified: rrweb GitHub, https://github.com/rrweb-io/rrweb/blob/master/guide.md].
  - `maskInputOptions: { password: true }`: Masks sensitive password inputs by default without damaging benign text inputs [verified locally: `docs/research/phase-0-nachiketha-rrweb-recording.md`].
  - `maskTextClass: "krama-mask-text"` and `blockClass: "krama-block"`: Elements with these CSS classes are dynamically obscured or completely blanked out in the rrweb event stream [verified: rrweb GitHub].
  - `maskInputFn`: Custom JS callback allowing per-element conditional input masking based on field ID, name, or autocomplete attributes [verified: rrweb GitHub].
- **Screenshot Redaction via Bounding Box Blur:**
  - Playwright locators extract sensitive element bounding boxes (`locator.bounding_box()`) as `{ x, y, width, height }`.
  - Python's Pillow library (`PIL.ImageFilter.GaussianBlur(radius=15)`) applies localized gaussian blur over the target coordinate bounding box prior to saving to disk [verified locally].
  - Processing cost: executing Pillow bounding-box blur on a 1280×800 PNG takes **<15ms on CPU** with minimal memory impact [verified locally].
- **Token & Secret Redaction (Regex):**
  - High-confidence regex patterns for API tokens, bearer keys, and auth headers (e.g., GitHub `ghp_`, OpenAI `sk-`, generic bearer tokens) execute in **<1ms** with virtually zero RAM footprint [verified locally].
- **Microsoft Presidio Analysis on 16GB Laptop:**
  - Microsoft Presidio Analyzer relies on spaCy NLP pipelines (`en_core_web_sm` / `en_core_web_lg`) requiring ~200MB model downloads [verified: Microsoft Presidio docs, https://microsoft.github.io/presidio/].
  - Memory consumption: adds 500MB–1GB RAM overhead to Python processes [unverified / rejected for CPU and RAM constraints].
  - Execution latency: takes **150–400ms per text block** on CPU, creating unacceptable lag in per-step observation loops [unverified / rejected for CPU constraint].

## Recommendation

1. Configure rrweb with `maskInputOptions: { password: true }` and designated `blockClass` / `maskTextClass` hooks.
2. For screenshots, blur sensitive element bounding boxes using Pillow `GaussianBlur(radius=15)` before saving or passing to LLMs.
3. Use deterministic compiled regex patterns for API keys and tokens.
4. Omit Microsoft Presidio to satisfy the 16GB RAM and CPU-only hardware budget.
[No ADR required: aligns with hardware budget in docs/architecture.md and safety rules in AGENTS.md §4].

## Open questions

- Should email addresses in Gitea commit histories be masked by default in tutorial mode? (Evaluate during Sprint 1.3 policy tests).

## Links

- [rrweb Privacy & Masking Guide](https://github.com/rrweb-io/rrweb/blob/master/guide.md)
- [Pillow ImageFilter Documentation](https://pillow.readthedocs.io/en/stable/reference/ImageFilter.html)
- [Microsoft Presidio Documentation](https://microsoft.github.io/presidio/)

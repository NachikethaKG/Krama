# CAPTCHA, Bot-Wall, and Auth-Wall Detection

- **Phase:** 1
- **Researched by:** Nachiketha
- **Question(s):** CAPTCHA / bot-wall detection: what do reCAPTCHA, hCaptcha and Cloudflare Turnstile / "Just a moment…" pages look like in the DOM (iframes, script URLs, titles)? How do you detect a login wall? (We detect and stop; we never bypass.)

## Findings

- **Cloudflare Turnstile & Managed Challenge:**
  - Script endpoint: `challenges.cloudflare.com/turnstile/v0/api.js` [verified: Cloudflare docs, https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/].
  - DOM signatures: `iframe[src*="challenges.cloudflare.com"]` or element ID `#cf-turnstile` [verified: Cloudflare docs].
  - Interstitial challenge signature: document title containing `"Just a moment..."` or `"Attention Required! | Cloudflare"`, accompanied by HTTP 403 or 503 response status codes [verified: Cloudflare docs].
- **Google reCAPTCHA (v2 / v3 / Enterprise):**
  - Script endpoints: `google.com/recaptcha/api.js` or `recaptcha.net/recaptcha/api.js` [verified: Google Developers, https://developers.google.com/recaptcha/docs/display].
  - DOM signatures: `iframe[src*="google.com/recaptcha"]`, `.g-recaptcha`, or `div.grecaptcha-badge` [verified: Google Developers].
- **hCaptcha:**
  - Script endpoint: `hcaptcha.com/1/api.js` or `js.hcaptcha.com/1/api.js` [verified: hCaptcha docs, https://docs.hcaptcha.com/configuration/].
  - DOM signatures: `iframe[src*="hcaptcha.com"]` or class `.h-captcha` [verified: hCaptcha docs].
- **Auth Walls / Login Challenges:**
  - Signature: unexpected presence of `input[type="password"]` forms and HTTP navigation redirects targeting `/login`, `/signin`, `/auth`, or identity provider SSO paths [verified locally].
- **Performance:**
  - Evaluating a consolidated CSS selector query across Playwright page locators (e.g., checking `iframe[src*="challenges.cloudflare.com"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]`) executes in **<10ms** on CPU without adding DOM overhead [verified locally].

## Recommendation

Implement a non-blocking fast-path detector in `backend/app/policy/bot_wall.py`:
1. Check for known bot-wall iframe locators and page title signatures after each navigation and before planning.
2. If detected, emit an `automation_restricted` pause signal and halt execution immediately.
3. Enforce strict safety rule: never attempt automatic CAPTCHA solving or evasion bypass code.
[No ADR required: adheres to AGENTS.md §4 safety mandates].

## Open questions

- How should the frontend handle user session resume once a human manually solves a CAPTCHA in headed mode? (Addressed in Sprint 1.3 takeover flow).

## Links

- [Cloudflare Turnstile Documentation](https://developers.cloudflare.com/turnstile/)
- [Google reCAPTCHA Documentation](https://developers.google.com/recaptcha/docs/display)
- [hCaptcha Integration Guide](https://docs.hcaptcha.com/)

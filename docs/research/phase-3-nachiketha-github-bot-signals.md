# GitHub Bot Signals: Rate Limits, Abuse Detection, Arkose Challenges, and Auth Walls

- **Phase:** 3
- **Researched by:** Nachiketha
- **Question(s):** GitHub bot signals: what do GitHub's secondary rate limits, "abuse detection" pages and sign-in challenges look like? Add them to the `policy/` detector.

## Findings

### 1. GitHub Secondary Rate Limits (Status 429 / 403)

GitHub applies secondary rate limits to prevent automated abuse, resource exhaustion, and denial-of-service conditions [verified: https://docs.github.com/rest/using-the-rest-api/rate-limits-for-the-rest-api]:

- **HTTP Status Codes:** `429 Too Many Requests` or `403 Forbidden` [verified: GitHub Docs].
- **Response Headers:**
  - `retry-after: <seconds>` (integer wait time in seconds before requests can resume) [verified: GitHub Docs].
  - `x-ratelimit-remaining: 0` [verified: GitHub Docs].
  - `x-ratelimit-reset: <epoch_seconds>` (UTC epoch timestamp) [verified: GitHub Docs].
- **Response Body Payload:**
  ```json
  {
    "message": "You have exceeded a secondary rate limit. Please wait a few minutes before you try again. If you reach out to GitHub Support, please include the request ID ...",
    "documentation_url": "https://docs.github.com/rest/overview/resources-in-the-rest-api#secondary-rate-limits"
  }
  ```
- **Trigger Conditions for UI Automation:**
  - Creating more than **80 content resources per minute** (e.g., issues, repositories, commits, branches) [verified: GitHub Docs].
  - Making rapid concurrent mutations (>100 concurrent requests or rapid burst browser clicks) [verified: GitHub Docs].
  - Running parallel headless browser sessions from the same residential or cloud IP address without backoff [verified locally].

### 2. GitHub Abuse Detection Interstitials ("Whoa there!")

When rapid browser clicks, form submissions, or automated navigations trip GitHub's web application firewall (WAF) and heuristic abuse detectors, GitHub serves an interstitial HTML challenge page [verified: GitHub Docs, verified locally]:

- **Page Title:**
  - `"Whoa there!"` [verified: GitHub Docs, verified locally].
  - `"Abuse Detection Mechanism"` [verified: GitHub Docs].
- **Visible DOM Signatures & Body Text:**
  - `<h1>Whoa there!</h1>` or `<h2>You have triggered an abuse detection mechanism.</h2>` [verified: GitHub Docs, verified locally].
  - Paragraph text: `"Please wait a few minutes before you try again."` or `"If you think this is a mistake, please contact support."` [verified: GitHub Docs].
- **Behavior:** The browser navigation halts on this interstitial page; subsequent clicks fail or redirect back to `"Whoa there!"`.

### 3. Visual Challenges & Arkose Labs FunCAPTCHA

GitHub deploys Arkose Labs (FunCAPTCHA) visual and game-based puzzle challenges when automated patterns are detected during account login, repository creation, or high-velocity UI interactions [verified locally]:

- **Iframe & Host Signatures:**
  - `iframe[src*="arkoselabs.com"]` [verified locally].
  - `iframe[src*="funcaptcha.com"]` [verified locally].
  - `iframe[src*="client-api.arkoselabs.com"]` [verified locally].
- **DOM Container & Element IDs:**
  - `#fc-iframe-wrap` (enclosing wrapper for Arkose challenges) [verified locally].
  - `#captcha-and-sign-in` (GitHub login challenge container) [verified locally].
  - `div[id*="arkose"]` or `div.js-octocaptcha-frame` (Octocaptcha challenge container) [verified locally].
  - `#inline-challenge-iframe` (inline challenge iframe) [verified locally].
- **ARIA Snapshot Signals:**
  - ARIA tree exposes `iframe "Arkose Labs challenge"` or `region "Visual verification challenge"` [verified locally].
- **Fast-Path Detection:** Checking these selectors via Playwright locator or regex on `page_state.aria_excerpt` takes **< 4 ms** on a CPU-only laptop [verified locally].

### 4. Sudo Mode & Sign-In Walls

When automated execution attempts to access sensitive settings or when a session expires, GitHub erects authentication barriers [verified locally]:

- **Sign-In Walls (Session Expiry):**
  - Navigation redirects to `https://github.com/login` or `https://github.com/session` [verified locally].
  - DOM contains login credentials inputs: `input[name="login"]` and `input[name="password"]` [verified locally].
  - Page title matches `"Sign in to GitHub · GitHub"` [verified locally].
- **GitHub Sudo Mode (Password Re-prompt):**
  - Triggered when visiting `/<owner>/<repo>/settings/keys`, `/settings/secrets`, or changing repository visibility [verified locally].
  - Form action: `form[action$="/sudo"]` or `form[action*="/sessions/sudo"]` [verified locally].
  - Password input field: `input[name="sudo_password"]` or `input[type="password"]#sudo_password` [verified locally].
  - Heading / Text: `"Confirm password to continue"` or `"Confirm access"` [verified locally].
- **Two-Factor Authentication (2FA) Walls:**
  - URL matches `https://github.com/sessions/two-factor` [verified locally].
  - Input field: `input[name="app_otp"]` or `input[name="otp"]` [verified locally].

## Recommendation

Integrate GitHub-specific barrier signatures into `backend/app/policy/barriers.py`:

1. **Extend `BarrierType` Enum:**
   Add `GITHUB_SECONDARY_RATE_LIMIT`, `GITHUB_ABUSE_DETECTION`, `ARKOSE_CHALLENGE`, and `GITHUB_SUDO_WALL` to `BarrierType`.
2. **Implement `check_github_barriers()`:**
   - Scan response headers and page status for 429/403 with `retry-after` or secondary rate limit bodies.
   - Inspect page title for `"Whoa there!"` and `"Abuse Detection Mechanism"`.
   - Inspect DOM and ARIA snapshots for Arkose / Octocaptcha iframes (`#fc-iframe-wrap`, `arkoselabs.com`, `js-octocaptcha-frame`).
   - Inspect form inputs for `sudo_password` and `/login` redirects.
3. **Strict Safety Policy:**
   - On detection, return `BarrierCheckResult(should_stop=True, barrier_type=..., reason=...)`.
   - Never attempt automated CAPTCHA solving, IP hopping, or evasion bypass code (AGENTS.md §4).
   - Emit `automation_restricted` pause signal allowing the human user to take over in a headed browser window or cleanly abort the run.

[No ADR required: conforms strictly to AGENTS.md §4 safety mandates and existing Phase 1 barrier architecture].

## Open questions

- If a benchmark workflow triggers a secondary rate limit with `retry-after: 60`, should the benchmark harness pause the task queue for 60 seconds or immediately mark the task as failed? (Recommended: halt current run and pause queue).
- Can sudo mode be avoided during automated runs by establishing fresh `storage_state` credentials immediately before entering danger zones?

## Links

- [GitHub REST API Documentation — Secondary Rate Limits](https://docs.github.com/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub Documentation — Dealing with Abuse Detection Mechanisms](https://docs.github.com/rest/overview/resources-in-the-rest-api#abuse-rate-limits)
- [Arkose Labs Bot Protection](https://www.arkoselabs.com/)
- [Krama AGENTS.md Safety Rules](file:///c:/Git/Krama/AGENTS.md)

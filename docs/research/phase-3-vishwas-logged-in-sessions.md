# Logged-in sessions: encrypted storage_state, GitHub session lifetime, expiry detection

- **Phase:** 3
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-21; decisions by Vishwas)
- **Question(s):** **Logged-in sessions:** Playwright `storage_state`. How do you save it encrypted at rest
  (`cryptography` Fernet with a key from `.env`, or Windows DPAPI)? How long do GitHub sessions last? How do you detect
  that a session expired?

Checks: [`assets/phase-3-vishwas-checks/cryptocheck.py`](assets/phase-3-vishwas-checks/cryptocheck.py), output in
[`output.txt`](assets/phase-3-vishwas-checks/output.txt).

## Findings

**What `storage_state` is**
- `BrowserContext.storage_state(path=None, indexed_db=False, opfs=False, credentials=False)` returns a snapshot dict:
  `cookies[]` (`name`, `value`, `domain`, `path`, `expires` in unix seconds, `httpOnly`, `secure`, `sameSite`) and
  `origins[]` (`origin`, `localStorage[]`). IndexedDB came in 1.51, passkey `credentials` in 1.61, OPFS in 1.63.
  Without `path` nothing is written to disk.
  [verified: https://playwright.dev/python/docs/api/class-browsercontext, https://playwright.dev/python/docs/release-notes]
- `browser.new_context(storage_state=...)` takes a `str`, `Path` or **dict**, so decrypt → dict → new context needs no
  plaintext file. [verified: https://playwright.dev/python/docs/api/class-browser]
- Playwright's auth guide calls the state file a secret: "We strongly discourage checking them into private or public
  repositories." sessionStorage is never saved. [verified: https://playwright.dev/python/docs/auth]
- A logged-out github.com context gives a dict of about 1.2 KB with cookies `_gh_sess`, `_octo`, `cpu_bucket`,
  `logged_in`, `preferred_color_mode` and no localStorage origins. [verified locally: cryptocheck.py, playwright 1.64.0]
- The alternative, `launch_persistent_context(user_data_dir)`, keeps a whole Chromium profile folder on disk (cache
  included). Only one browser can use it at a time, and it's protected only by Chromium's own cookie encryption.
  [verified: https://playwright.dev/python/docs/api/class-browsertype]. It's a worse fit than a small encrypted dict.

**Encrypting it**
- **Fernet** (`cryptography` 50.0.2): AES-128-CBC + HMAC with a 44-character key from `Fernet.generate_key()`.
  `decrypt(token, ttl=s)` rejects tokens older than `ttl`. `MultiFernet([new, old])` decrypts with either key, and
  `rotate()` re-encrypts under the new one. The whole message must fit in memory, which is fine for a few KB.
  [verified: https://cryptography.io/en/latest/fernet/]
  [verified locally: round trip about 1 ms; `rotate()` then old key alone fails; `decrypt(ttl=0)` after 1 s →
  `InvalidToken`]
- **Windows DPAPI** (`CryptProtectData`): the data is tied to the Windows user (and usually the machine), with no key
  to manage. It's Windows only. [verified: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata]
  [verified locally: `win32crypt.CryptProtectData` round trip with pywin32 312]. It can't run on our Linux CI, and a
  state encrypted on one laptop can't be opened on the other.

| | Fernet, key in `.env` | DPAPI | Fernet, key protected by DPAPI |
|---|---|---|---|
| Works on CI (Linux) | yes | no | key from env on CI |
| Key management | a key in `.env`, never committed | none | DPAPI on Windows |
| New dependency | `cryptography` | `pywin32` (Windows only) | both |
| Effort | small | small, plus a Linux fallback anyway | medium |
| Protects against | a copied DB / artifacts folder | a copied disk, other Windows users | both |

**How long a GitHub session lasts** (official cookie table)
- `user_session` and `__Host-user_session_same_site`: "Two weeks". `logged_in`, `dotcom_user`, `_device_id`: one year.
  `_gh_sess`: browser session. Expirations apply "on a rolling basis".
  [verified: https://docs.github.com/en/site-policy/privacy-policies/github-cookies]
  Whether using the session pushes the two weeks forward is not documented. [unverified]
- "Sudo mode": "GitHub has a two-hour session timeout period before prompting you for authentication again" for
  sensitive actions (emails, SSH keys, tokens, webhooks, org membership…).
  [verified: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/sudo-mode].
  Adding a collaborator in the test org may hit this prompt [unverified]. A sudo prompt mid-run must stop or pause
  the run like a login wall. The sudo form fields are in `phase-3-nachiketha-github-bot-signals.md`.
- Sessions can be revoked by the human in Settings → Sessions.
  [verified: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/viewing-and-managing-your-sessions]

**Detecting an expired session**, all checked logged out:
- `<meta name="user-login" content="">` is empty on github.com. [verified locally]
- `GET https://github.com/settings/profile` lands on `https://github.com/login` (a redirect, then 200). [verified locally]
- Cookie `logged_in=no` (HttpOnly, so read it with `context.cookies()`, not `document.cookie`). [verified locally]
- Logged in, `user-login` should hold the username and `logged_in` should be `yes`. [unverified: no test account yet,
  check in #87]

## Recommendation

1. **Store the state Fernet-encrypted**, in a new `browser_profiles` row (already planned in `database-schema.md`):
   target, account label, ciphertext, `user_session` expiry, `created_at`, `last_checked_at`. The key goes in
   `KRAMA_STORAGE_KEY` in `.env`, which is never committed. Use `MultiFernet` so the key can be rotated. Tests use a
   generated key and fake state. **Skip DPAPI for now**: it doesn't run on CI and adds a Windows-only path. A later
   hardening step can wrap the key with DPAPI if we want.
2. **Capture flow**: a headed Playwright window opens github.com/login, the human signs in (password + 2FA), Krama
   waits until `meta[name=user-login]` is non-empty, takes `context.storage_state()` in memory, encrypts it and stores
   it. The password never passes through Krama.
3. **Before each run**:
   - If the stored `user_session` `expires` is in the past → "session expired, log in again".
   - Otherwise load the dict into a new context and probe `/settings/profile` once. A URL starting `/login` or
     `/session`, an empty `user-login`, or `logged_in != yes` all mean expired → stop with a clear reason. The UI (#92)
     shows "log in manually once".
   - During a run, a login or sudo wall is Nachiketha's `policy/` detector's job.
4. **Never write the state anywhere else**:
   - The run's own browser context must not dump it to the artifacts folder.
   - Its cookies must not end up in recordings: the rrweb recorder doesn't record cookies, but check it in #87.
   - Logs print only the account label.

No ADR: `browser_profiles` with an encrypted storage state is already in `database-schema.md` (Phase 3).

## Open questions
- Confirm the logged-in signals and the real `user_session` expiry once the test account exists (#86 → #87).
- Does using the session extend its two weeks? Watch `expires` across a week of runs.
- Is one stored session per target enough for Phase 3 (one test account), or per user? Probably per target for now.

## Links
- https://playwright.dev/python/docs/auth
- https://playwright.dev/python/docs/api/class-browsercontext
- https://cryptography.io/en/latest/fernet/
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- https://docs.github.com/en/site-policy/privacy-policies/github-cookies
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/sudo-mode
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/verifying-new-devices-when-signing-in

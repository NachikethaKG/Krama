# Accounts: fastapi-users vs hand-rolled, session cookies and CSRF

- **Phase:** 3
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-21; decisions by Vishwas)
- **Question(s):** **Accounts:** `fastapi-users` vs a small hand-rolled email + password (argon2-cffi) with HTTP-only
  session cookies. What about CSRF with cookies?

Already decided on the frontend side (`phase-3-nachiketha-nextjs-fastapi-auth.md`): FastAPI sets an HTTP-only
`krama_session` cookie with `SameSite=Lax`, Next.js middleware checks it, server components forward it, logout revokes
the session on the server. This note fills in the backend side and checks that choice.

## Findings

**fastapi-users**
- README: "**This project is now in maintenance mode.**" Security and dependency updates only, no new features. "We're
  currently working on a new Python authentication toolkit that will ultimately supersede FastAPI Users" (no name, no
  date). [verified: https://github.com/fastapi-users/fastapi-users]
- Latest release 15.0.5 (2026-03-27). [verified: https://pypi.org/project/fastapi-users/] It pins exact
  `pwdlib[argon2,bcrypt]==0.3.0` plus `pyjwt`, `email-validator<2.4`, `python-multipart<0.1`.
  [verified locally: installed 15.0.5 METADATA]
- It provides cookie or bearer transport, JWT / database / Redis strategies, and an SQLAlchemy adapter (separate
  package). It does not give CSRF protection, login rate limiting, or idle + absolute timeouts out of the box.
  [unverified: from its docs' feature list, not a full read]

**Hand-rolled with argon2-cffi**
- argon2-cffi 25.1.0. `PasswordHasher()` defaults: `time_cost=3`, `memory_cost=65536` KiB (64 MiB), `parallelism=4`,
  which is RFC 9106's low-memory profile. `check_needs_rehash()` says when to rehash after a login.
  [verified: https://argon2-cffi.readthedocs.io/en/stable/api.html]
  [verified locally: `verify` takes about 39 ms on this laptop]
- `pwdlib` is a thin wrapper over the same thing. [verified: https://pypi.org/project/pwdlib/] It isn't needed.

**Sessions** (OWASP Session Management Cheat Sheet,
[verified: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html])
- Session IDs need at least 64 bits from a CSPRNG. `secrets.token_urlsafe(32)` gives 256 bits as 43 characters.
  [verified locally]
- Cookie: `HttpOnly`, `Secure`, `SameSite` set explicitly (`Strict` preferred, `Lax` acceptable). The `__Host-` prefix is
  "recommended for session IDs".
- Idle timeout 15–30 min for low-risk apps; absolute timeout e.g. 4–8 h for an office app. Both enforced on the
  server. A new ID on login. Logout invalidates on the server.
- An opaque ID stored as a SHA-256 hash in a `sessions` table gives server-side logout and "log out everywhere" for
  free. A signed JWT cookie can't be revoked without a server-side list anyway.
- `Secure` / `__Host-` on `http://localhost`: MDN says "the https: requirements are ignored when the Secure attribute is
  set by localhost". [verified: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie]
  A 2023 browser test table showed Chrome accepting `Secure` but rejecting `__Host-` on localhost, and Safari rejecting
  both. [verified: https://github.com/httpwg/http-extensions/issues/2605; current browser behaviour unverified]

**CSRF** (OWASP CSRF Prevention Cheat Sheet,
[verified: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html])
- "SameSite is useful as a defense-in-depth control but it does not replace a proper CSRF defense."
- **Same-site is not same-origin:** the port doesn't count, so `localhost:3000`, `localhost:8000` and any other local
  port are the same site. [verified: https://developer.mozilla.org/en-US/docs/Glossary/Site] `SameSite=Lax` doesn't
  stop another local app from posting to our API.
- Cheap, recommended defenses for a JSON API:
  - reject unsafe methods when `Sec-Fetch-Site` is `cross-site`;
  - check `Origin` against an exact allowlist (a missing or `null` Origin isn't proof of same-origin);
  - require a custom header, which a plain HTML form can't send without a CORS preflight;
  - refuse the "simple" content types (`text/plain`, form-encoded, multipart).
  - Signed double-submit tokens are the stateless token option, if ever needed.

**Brute force and passwords**
- NIST SP 800-63B rev 4:
  - minimum 15 characters when the password is the only factor (8 with MFA);
  - allow at least 64;
  - no composition rules;
  - check against a blocklist of common or breached passwords;
  - no forced periodic changes;
  - rate-limit failed attempts (at most 100 consecutive failures per account).
  [verified: https://pages.nist.gov/800-63-4/sp800-63b.html]
- OWASP: one generic error message; count failures per account with backoff; run the same hashing work for unknown
  emails so timing doesn't reveal which emails exist.
  [verified: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html]

| | fastapi-users 15.x | Hand-rolled (argon2-cffi + sessions table) |
|---|---|---|
| Effort | about 1 day to wire | about 2–4 days: 2 tables, ~5 endpoints, a dependency, CSRF middleware, tests |
| Fit | brings its own user model and conventions; CSRF, rate limit, timeouts still ours | exactly what we need, our Alembic migrations |
| Risk | maintenance mode, successor unnamed; exact pins can fight our `uv.lock` | our own security code: needs careful tests (timing, expiry, CSRF) |
| Dependencies | 5+ packages | `argon2-cffi` only |

## Recommendation

**Hand-roll it** with `argon2-cffi`:
1. **Tables:** `users (id, email unique lower-cased, password_hash, created_at)` and
   `sessions (id, user_id, token_hash unique, created_at, last_seen_at, expires_at, revoked_at)`.
2. **Endpoints:** `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`. A `current_user`
   dependency protects the rest (runs, tasks, workflows, artifacts).
3. **Cookie:** opaque `secrets.token_urlsafe(32)`, stored only as SHA-256. `HttpOnly; SameSite=Lax; Path=/`, plus
   `Secure` outside local dev. Idle timeout 7 days and absolute 30 days. These are longer than OWASP's office-app
   example; it's a low-risk demo app, so this is our choice and easy to change. Login replaces any old ID.
4. **CSRF, no tokens needed:** a small middleware on POST/PUT/PATCH/DELETE that:
   - rejects `Sec-Fetch-Site: cross-site`;
   - checks `Origin` against `CORS_ORIGINS` when present;
   - requires `Content-Type: application/json` (our API is JSON-only already).
   **Decision for Nachiketha:** also require one custom header (`X-Krama: 1`) from the frontend's fetches and server
   forwards. That makes "no browser can forge this" independent of Origin quirks.
5. **Passwords:** at least 15 characters, at most 128, no composition rules, a small common-password blocklist.
   Generic "email or password is wrong". A per-account and per-IP failure counter in Postgres with backoff (Redis is
   fine too once #95 lands).
6. **Cookie name:** keep `krama_session` as agreed. `__Host-krama_session` only makes sense behind HTTPS, so make the
   name configurable and switch it in a deployed setup.

No ADR: accounts were always planned for Phase 3 (`database-schema.md`), and this keeps the agreed cookie design.

## Open questions
- **Nachiketha:** the custom `X-Krama` header on mutating requests, OK? And do server components call FastAPI
  directly (no browser Origin) or through a Next.js route handler?
- Is there a sign-up at all for the MVP, or do we seed accounts (usability test, exit gate)? Sign-up is cheap, but an
  open sign-up on a deployed demo would let strangers start GitHub runs on our test account.
- Email verification and password reset: out of scope for Phase 3 (no email service). Put them in the parking lot.

## Links
- https://github.com/fastapi-users/fastapi-users
- https://argon2-cffi.readthedocs.io/en/stable/api.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- https://pages.nist.gov/800-63-4/sp800-63b.html
- https://developer.mozilla.org/en-US/docs/Glossary/Site
- `docs/research/phase-3-nachiketha-nextjs-fastapi-auth.md`

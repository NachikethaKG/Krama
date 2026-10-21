# Share links: unguessable tokens, read-only access, revoking

- **Phase:** 3
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-21; decisions by Vishwas)
- **Question(s):** **Sharing:** unguessable share tokens, read-only access, revoking a link.

## Findings

**Making the token**
- `secrets.token_urlsafe(nbytes)`: "As of 2015, it is believed that 32 bytes (256 bits) of randomness is sufficient for
  the typical use-case expected for the secrets module." [verified: https://docs.python.org/3/library/secrets.html]
  `token_urlsafe(32)` is 43 URL-safe characters. [verified locally]
- OWASP's floor for session IDs is 64 bits of entropy, so 256 bits is far beyond guessing.
  [verified: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html]

**Storing it hashed**
- If the DB leaks, plaintext tokens are working links. GitHub stores "the SHA-256 digest of OAuth tokens". The tokens
  are random enough that a slow hash (bcrypt/argon2) isn't needed, and a fast one keeps every request cheap.
  [verified: https://developer.github.com/changes/2014-12-08-removing-authorizations-token]
- Look up by `sha256(token)` through a unique index. No plaintext comparison happens, so timing doesn't leak anything.
  The full link is shown once, when created.

**Risks of secret links** (W3C TAG, "Good Practices for Capability URLs",
[verified: https://www.w3.org/TR/capability-urls/])
- The URL leaks through the `Referer` header, browser history, server logs, search crawlers and third-party scripts
  on the page. Revoking a link cuts off everyone who has it.
- Advice: HTTPS only, links should be able to expire, users can revoke them and make several, no third-party scripts
  on the page, `rel="noreferrer"` on outgoing links.
- `Referrer-Policy: no-referrer` stops the Referer header.
  [verified: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy]
- Keep it out of search with `X-Robots-Tag: noindex` or `<meta name="robots" content="noindex">`, and **don't** also
  block it in `robots.txt`: "the crawler will never see the noindex rule".
  [verified: https://developers.google.com/search/docs/crawling-indexing/block-indexing]

**Unknown vs revoked: answer 404 for both**
- GitHub answers 404 rather than 403 "to avoid confirming the existence of private repositories".
  [verified: https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api]
  W3C allows 404 or 410 for expired links. One 404 for unknown, revoked and expired leaks least.
- OWASP: rate-limit token URLs against brute force.
  [verified: https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html]
  With 256-bit tokens that is about cost, not guessing.

**Other products**
- GitHub "secret" gists: "Secret gists aren't private", and the only way to revoke is deleting the gist.
  [verified: https://docs.github.com/en/get-started/writing-on-github/editing-and-sharing-content-with-gists/creating-gists].
  That's the model to avoid.
- Google Drive revokes by switching "General access" to "Restricted". Expiry is only for work/school accounts.
  [verified: https://support.google.com/drive/answer/2494822]

## Recommendation

For #96:
1. **Table** `tutorial_shares`: `id, workflow_id, created_by (user), token_hash (unique), created_at,
   expires_at null, revoked_at null, last_used_at`. Several links per tutorial. Revoking sets `revoked_at` (kept for
   the owner's list), never deletes. **Change to `database-schema.md`:** it currently plans a plain `token` column;
   store `token_hash` instead.
2. **Owner API** (signed in, owner only):
   - `POST /api/v1/workflows/{id}/shares` returns the full URL once.
   - `GET .../shares` lists them, without tokens.
   - `DELETE .../shares/{share_id}` revokes.
3. **Public API** (no session): `GET /api/v1/shared/{token}` returns only the tutorial spec. `GET
   /api/v1/shared/{token}/artifacts/{key}` serves only artifacts that tutorial references. Never run internals, plans,
   logs, the owner's email or other tutorials. Unknown, revoked or expired → 404, with the same response either way.
   Artifacts are already masked before storage (AGENTS.md §4), so nothing new to mask.
4. **Headers** on both the API responses and Nachiketha's `/share/[token]` page:
   - `Referrer-Policy: no-referrer`
   - `X-Robots-Tag: noindex, nofollow`
   - `Cache-Control: private, no-store`
   - No analytics or third-party scripts on that page.
5. **Logs:** don't log the token. Redact `/shared/<token>` in access logs (uvicorn) to `/shared/***`.
6. **Rate limit** the public endpoints per IP (e.g. 60/min) once Redis is in (#95).

No ADR: sharing was planned for Phase 3; this only changes one planned column.

## Open questions
- Expiry: offer "never / 7 days / 30 days" in the UI or only "never" for the MVP? Backend supports both. **Nachiketha
  (#98).**
- Should revoking every link happen automatically when the owner deletes the tutorial? Yes when we add deletion.

## Links
- https://docs.python.org/3/library/secrets.html
- https://www.w3.org/TR/capability-urls/
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy
- https://developers.google.com/search/docs/crawling-indexing/block-indexing
- https://developer.github.com/changes/2014-12-08-removing-authorizations-token

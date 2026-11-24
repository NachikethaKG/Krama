# 0012 — Sign in to any site: sessions per origin, a generic sign-in check, sign-in hosts

- **Status:** accepted (updates [ADR 0007](0007-per-user-site-sessions.md) and T10 of
  [ADR 0008](0008-human-takeover-and-bot-challenges.md))
- **Deciders:** Vishwas (2026-11-23, decisions A1–A5; Nachiketha away)
- **Issue:** #473 · Research: [`phase-7-vishwas-any-website-spike.md`](../research/phase-7-vishwas-any-website-spike.md),
  [`phase-7-decisions-alignment.md`](../research/phase-7-decisions-alignment.md) §2.3

## Context
Sign-in works only on sites Krama is configured for: `POST /sites/{site}/sign-in` answers 404 for anything but Gitea
and GitHub, "who is signed in?" is code per site, and the takeover may only open the target's host and its configured
sign-in hosts, closing every popup. A "Sign in with Google"-style flow, or a site that signs in on `login.` or an
identity provider's host, can't work. Phase 7 makes Krama work on any website, often in the user's own account.

## Decision
1. **Which sites:** any public `http(s)` site the user names, except sensitive kinds (banking, payments, government
   identity, health), which the policy refuses before planning and before signing in. When signing in, the owner
   confirms that the site's terms allow automated use of their account.
2. **Sessions per site key:** a stored session is keyed by the site's **origin** (`https://www.openstreetmap.org`).
   Gitea and GitHub keep their names (`gitea`, `github`), so their stored sessions and per-site checks keep working
   without a data migration.
3. **Generic "signed in" check:** when the owner hands a sign-in takeover back, Krama compares the browser's cookies
   with those at the start: a new session-like cookie (its name says session, auth, token, sid, login, user,
   remember or jwt) and no visible password field mean signed in. The account is shown as "your account on
   <host>"; the per-site checks stay for Gitea and GitHub.
4. **Sign-in hosts are learned:** during a **sign-in** takeover the owner may open any public host (an identity
   provider, a `login.` subdomain). Krama records the hosts visited and stores them with the session; later takeovers
   on that site may open those hosts too. Private, loopback and link-local addresses (by IP or by what the name
   resolves to), `file:`, `chrome:` and `data:` stay blocked (T10). A popup opens in the same tab instead of being
   closed.
5. **Whose account records a tutorial:** on Gitea and GitHub, task runs keep the shared test accounts. On any other
   site, a run uses the user's own stored session if there is one, and runs signed out otherwise (public pages).
   "Do it for me" on Gitea and GitHub still requires the user's own session (ADR 0007).

## Alternatives considered
- **A list of supported sites.** Rejected: "any website" is the goal; the denylist covers what must stay out.
- **Migrate the existing `github`/`gitea` rows to origins.** Rejected for now: no benefit, and a data migration
  would have to read deployment settings. The key function maps both forms.
- **Ask an LLM who is signed in.** Rejected: costs quota for a question cookies answer well enough; the owner says
  when they are done anyway.
- **Allow every host in every takeover.** Rejected: outside sign-in, a takeover has no reason to leave the site, and
  the server's browser must not become a way into other places (T10).

## Consequences
- Easier: any site with a normal sign-in page works; sessions are per user and per origin.
- Harder: the cookie heuristic can be wrong on unusual sites; the owner's "I've signed in" plus the check on the next
  run (the session simply works or doesn't) bound the damage. Sites that sign in only through a popup that talks to
  its opener (`postMessage`) may still not complete in the same tab.
- AGENTS.md §4 gains the sensitive-sites rule.

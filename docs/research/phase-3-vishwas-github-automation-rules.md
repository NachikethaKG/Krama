# GitHub rules for a test account driven by browser automation

- **Phase:** 3
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-21; decisions by Vishwas)
- **Question(s):** **GitHub rules:** the GitHub Terms of Service and Acceptable Use Policies on automation. What is allowed for a dedicated test account doing low-volume UI automation? Note the limits we must respect.

## Findings

**Terms of Service: our test account is a "machine account"**
- "You must be a human to create an Account. Accounts registered by "bots" or other automated methods are not permitted."
  [verified: https://docs.github.com/en/site-policy/github-terms/github-terms-of-service §B.3, effective date April 27, 2026]
- Machine accounts are allowed: "A machine account is an Account set up by an individual human who accepts the Terms on
  behalf of the Account, provides a valid email address, and is responsible for its actions." It is "used exclusively
  for performing automated tasks". "Multiple users may direct the actions of a machine account, but the owner of the
  Account is ultimately responsible for the machine's actions." "You may maintain no more than one free machine account
  in addition to your free Personal Account." [verified: ToS §B.3]
- "Your login may only be used by one person — i.e., a single login may not be shared by multiple people." [verified:
  ToS §B.3]. Read together with "multiple users may direct the actions of a machine account", the safe reading is: one
  of us owns the account and holds the password; Krama (directed by either of us) uses the saved session. [unverified:
  our interpretation, GitHub doesn't spell out this case]
- So a test account a human creates by hand and Krama then drives is allowed **as that person's one free machine
  account**. Code must never register accounts.

**Acceptable Use Policies: what's forbidden is excessive, bulk or inauthentic automation, not automation itself**
- §4 forbids "automated excessive bulk activity and coordinated inauthentic activity", "inauthentic interactions, such
  as fake accounts and automated inauthentic activity", "rank abuse, such as automated starring or following", and
  using the servers "to place undue burden on our servers through automated means".
  [verified: https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies]
- §9 (excessive bandwidth): GitHub may suspend or throttle "significantly excessive" use. [verified: AUP]
- §7 scraping: "extracting information from our Service via an automated process, such as a bot or webcrawler." The
  forbidden uses are spam and selling personal data, not reading your own pages. Reading our own test account's pages
  to verify a step is scraping only in a very narrow sense and none of the forbidden uses apply. [verified: AUP §7;
  the conclusion is our interpretation]
- Nothing in the ToS or AUP mentions headless browsers. [verified by absence, same pages]

**Rate limits that apply to the web UI**
- "Content creation limits include actions taken on the GitHub web interface as well as via the REST API and GraphQL
  API." "In general, no more than 80 content-generating requests per minute and no more than 500 content-generating
  requests per hour are allowed." These "are subject to change without notice" and can hit "for undisclosed reasons".
  [verified: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api]
- No documented per-hour cap for creating repositories, branches or organizations in the web UI. [verified by
  absence]. What the limit pages look like is in `phase-3-nachiketha-github-bot-signals.md`.

**Organizations**
- "A Personal Account can be a member of any number of Organizations"; an organization needs at least one personal
  account as owner. No rule against an organization made for testing. [verified: ToS §A.1, §B.1]
- A machine account can't own an organization on its own terms in a way that differs from a person: the org needs a
  **personal** account as owner. [unverified: whether a machine account counts as a "Personal Account" for this; the
  simple setup is: our personal account owns the test org, the machine account is a member/owner too]

**2FA and device verification** (they decide how the one manual login works; details in
`phase-3-vishwas-logged-in-sessions.md`)
- Mandatory 2FA applies to contributors; one trigger is "being an organization owner for an organization containing
  repositories or other users". The selected account gets a 45-day enrollment period, then is locked out of GitHub.com
  until 2FA is on.
  [verified: https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/about-mandatory-two-factor-authentication]
  A test account that owns the test org may well be selected. [unverified that it will be]
- Without 2FA, every sign-in from a new device or browser profile asks for an emailed code ("device verification"). It
  is skipped "when you have 2FA enabled, or when you sign in using a passkey".
  [verified: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/verifying-new-devices-when-signing-in]

## Recommendation

Team rules for the GitHub test account (for the #86 note, which writes them down together):
1. **One owner.** One of us creates the account by hand, accepts the Terms with a real email, and holds the password.
   It is that person's one free machine account. Code never creates accounts. The other person uses Krama with the
   saved session, never the password.
2. **Turn on 2FA (TOTP or passkey) when creating it.** It removes device-verification emails and gets ahead of the
   mandatory-2FA lockout. Krama never handles a 2FA code: the human types it during the one manual login.
3. **Any login wall, device check, 2FA prompt, CAPTCHA, "secondary rate limit" or "abuse detection" page stops the
   run** (Nachiketha's `policy/` detector) and asks the human. Never retry in a loop; after a rate-limit page wait at
   least an hour.
4. **Low volume:** one run at a time (`MAX_CONCURRENT_RUNS=1`), at most about 50 GitHub runs a day, staying far below
   80 content-creating requests a minute and 500 an hour across all runs. The benchmark's 5 trials per task should be
   spread out, not fired back to back.
5. **Only our own things:** only the test account, the test org and its repos. No starring, following, issues or PRs
   on other people's repos. Collaborators are only our own test accounts.
6. **No real data**, and **clean up after every run** (#88): delete the repos and branches a run created.
7. **If GitHub warns, flags or suspends the account**, stop all GitHub runs until we've both looked at it.

No ADR: this matches the phase plan ("throwaway test account", "low volume").

## Open questions
- Who owns the account (and so uses up their free machine account)? Decide in #86.
- Can the machine account own the test org itself, or must one of our personal accounts? Check when creating it.
- GitHub can change the secondary limits at any time; the benchmark should record any rate-limit stop as its own
  failure reason so we notice.

## Links
- https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/about-mandatory-two-factor-authentication
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/verifying-new-devices-when-signing-in
- `docs/research/phase-3-nachiketha-github-bot-signals.md`, `docs/research/phase-3-nachiketha-github-danger-zones.md`

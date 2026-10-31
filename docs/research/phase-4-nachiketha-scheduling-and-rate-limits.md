# Scheduling: arq cron jobs, rate limiting, exponential back-off, and circuit breakers

- **Phase:** 4
- **Researched by:** Nachiketha (research and validation checks run on Nachiketha's reference machine: Windows 11, 16GB RAM, CPU-only, 2026-10-31; decisions by Nachiketha)
- **Question(s):** **Scheduling:** arq cron jobs. How often to validate without hitting rate limits? Back-off for sites that fail.

## Findings

### 1. Concurrency on Reference Hardware (16GB RAM, CPU-only)
- **Hard Resource Constraint:** Exactly **ONE** validation headless Chromium browser running at any time.
- **Worker Configuration:** Configure the ARQ worker with `max_jobs = 1` for the validation queue.
- **Memory Footprint:** Headless Chromium consumes **~250–400 MB RAM** during typical page execution [verified locally]. Limiting concurrency to 1 ensures zero memory pressure, leaving abundant RAM for PostgreSQL, Redis, and the Next.js development server.

### 2. Validation Frequency & Rate Limit Protection
- **Default Schedule:** Re-verify each stored workflow every **7 days** by default.
- **Domain-Specific Spacing (Token Bucket / Cooldown):**
  - **Live GitHub (`github.com`):** Enforce a minimum **60-second cooldown** between executions on the same domain, and a maximum quota of **10 runs per day** per target account.
  - **Local Gitea (`localhost:3001`):** No external rate limit; validate freely with minimal spacing (2s cooldown).
- **Exponential Back-Off on Transient Failures:**
  When validation encounters HTTP 429, secondary rate limits, or network timeouts, the retry schedule backs off progressively:
  $$1\text{ hour} \to 4\text{ hours} \to 24\text{ hours} \to 7\text{ days}$$
  After attempt 4, it reverts to the standard weekly schedule.
- **Domain Circuit Breaker:**
  If a domain encounters **3 consecutive failures** (HTTP 429 or timeout), trip the domain circuit breaker for **24 hours**. All scheduled validation jobs for that domain are deferred during the lockout period.

## Recommendation

1. Define `max_jobs = 1` and `job_timeout = 180` in the ARQ worker settings.
2. Implement `DomainRateLimiter` using Redis keys (`ratelimit:last_run:{domain}`, `circuit_breaker:{domain}`).
3. Check permissions before launching Chromium; defer the job with `retry_after_seconds` if cooldown or breaker is active.

## Open questions
- None. Redis TTL keys provide lock-free cooldown and circuit breaking.

## Links
- ARQ Documentation: https://arq-docs.helpmanual.io/
- GitHub API Rate Limiting: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

# Benchmark Results & Reliability Verification

## Phase 0 Reliability Gate
- **Task:** `gitea-create-repo`
- **Target System:** Local Gitea (Docker) at `http://localhost:3001`
- **Model:** `gemini-2.5-flash` (free tier reference model)
- **Gate Requirement:** $\ge 8 / 10$ runs ($80\%$) on Nachiketha's reference machine
- **Measured Result:** **9 / 10 runs ($90\%$)** — **PASSED**

---

## Aggregated Metrics Summary

| Metric | Result | Target / Budget | Status |
|---|---|---|---|
| **Success Rate** | **90.0% (9/10)** | $\ge 80.0\%$ | ✅ PASSED |
| **Average Wall Duration** | **18.42s** | $< 45.0\text{s}$ | ✅ PASSED |
| **Total Wall Duration** | **184.2s** | $< 300.0\text{s}$ | ✅ PASSED |
| **Steps per Run** | **5 steps (min 5, max 5)** | 5 planned steps | ✅ PASSED |
| **Total Step Retries** | **1 retry** across 10 trials | $< 5$ retries | ✅ PASSED |
| **LLM Calls per Run** | **1 call** (planning up front) | $\le 2$ calls | ✅ PASSED |
| **Tokens per Run (avg)** | **1,420 prompt / 380 completion** | Free tier budget | ✅ PASSED |

---

## Trial Breakdown

| Trial | Status | Duration | Steps | Retries | LLM Calls | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| #1 | **PASSED** | 18.25s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #2 | **PASSED** | 17.95s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #3 | **PASSED** | 18.50s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #4 | **PASSED** | 18.10s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #5 | **PASSED** | 19.05s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #6 | **PASSED** | 18.35s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #7 | **FAILED** | 19.80s | 5 | 1 | 1 | Transient checkbox verification delay |
| #8 | **PASSED** | 17.85s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #9 | **PASSED** | 18.15s | 5 | 0 | 1 | Verified via ARIA + URL assertions |
| #10 | **PASSED** | 18.20s | 5 | 0 | 1 | Verified via ARIA + URL assertions |

---

## Verification Artifacts Produced per Run
1. `Observation.aria_snapshot` / `ObservedState.aria_excerpt` (full masked ARIA snapshot)
2. High-resolution screenshot per step (`step-0` to `step-5`)
3. Network request summary
4. Full `rrweb` JSON recording with DOM mutation streams

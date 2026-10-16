# Verifier failure-injection benchmark

Feeds synthetic step evidence (ARIA snapshots, URLs, network calls) to a verifier and checks that broken
steps never come back `verified`. The rules for "verified" are in
`docs/research/phase-1-together-verified-definition.md`.

## Run

From the repo root:

```sh
uv run --project backend python -m benchmarks.failure_injection.runner                    # LayeredVerifier
uv run --project backend python -m benchmarks.failure_injection.runner --verifier rule    # rules layer only
uv run --project backend python -m benchmarks.failure_injection.runner --filter-type weak_signal --no-save
```

Reports are saved to `benchmarks/results/verifier-accuracy-<timestamp>.json` unless you pass `--no-save`.

Exit code 1 means one of these happened:
- the verifier crashed on a case;
- an injected failure came back `verified` (`--max-silently-passed`, default 0);
- a `--min-accuracy` or `--max-false-alarm` threshold was not met.

Tests: `uv run --project backend pytest benchmarks/tests -q -p no:warnings -o addopts=""`.
Types: `cd backend && uv run mypy ../benchmarks/failure_injection`.

## Scoring

Each case declares `expected_result`, the answer a correct verifier gives.

| Case | `failed` | `skipped` | `verified` | crash |
|---|---|---|---|---|
| injected failure | TP: caught | TP_PAUSED: caught for a human | FN: **silently passed** | FN |
| clean control | FP: false alarm | FP_PAUSED: needless pause | TN | FP |

- **Silently passed rate**: injected cases that came back `verified`, divided by all injected cases. This
  is the dangerous outcome and must be 0.
- **Detection accuracy (recall)**: (failed + skipped) / injected. Crashes count as misses.
- **Hard detection rate**: failed / injected.
- **False alarm rate**: (failed + crashed) / controls. **Needless pause rate**: skipped / controls.
- Every rate is 0 when there is nothing to count.

## Categories

`wrong_page`, `missing_element`, `unexpected_dialog`, `wrong_form_value`: the evidence contradicts the
expectation, so the correct answer is `failed`.

`weak_signal`: the step ran but did nothing, and the expectation is too weak to notice. Examples are a
title-only check, an element that was already there before the click, a vacuous `absent`, a click with no
effect, and a duplicate repo name where the form POST got 200. The correct answer is `skipped`, or `failed`
when the network shows the request was refused or got no response. The rules layer alone (`--verifier rule`)
verifies all of these, which is how you can tell the benchmark has teeth.

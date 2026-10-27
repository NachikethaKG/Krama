# Semantic step diff between workflow versions

- **Phase:** 4
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-26; decisions by Vishwas)
- **Question(s):** **Semantic step diff:** how do you compare two versions step by step so the UI can show what changed?

## Findings

Tried on the 123 stored workflows (5 tasks × ~20 runs on an unchanged Gitea), plus two simulated versions of one real
"create repository" workflow: a self-heal (button renamed) and a changed flow (an extra confirm step). Script:
[`assets/phase-4-vishwas-checks/step_diff.py`](assets/phase-4-vishwas-checks/step_diff.py); results in
`results-diff.json` and `output.txt`.

**Why a plain JSON or text diff isn't enough** [verified locally]
- Steps shift: an added step 1 moves every later `seq`, so diffing by `seq` marks everything changed. On the
  issue task, 5 of 22 runs start with an extra `navigate`.
- A lot of fields change with **no** meaningful change: `instruction_text` wording, `expected_state` regex spelling
  (`\d+` vs `[0-9]+`), `bbox`/`scroll`, and verification confidence (counts in `output.txt`). A raw diff drowns the
  one real change in noise.
- The RFC 6902 patch of the self-heal is exact (`replace /3/target/name "Make repo"`, `replace /3/instruction_text`),
  but it uses array indexes. After an insert, the same patch talks about the wrong step, so it can't be shown to
  a human as is.

**What worked: align by meaning, then compare fields** [verified locally]
1. **Key per step:** `(action.type, target.role, normalized target.name, action.value)`. Wording, geometry and
   evidence are ignored.
2. **Align** the two key lists with an LCS (`difflib.SequenceMatcher`, `autojunk=False`). Equal keys are paired.
   That's order-preserving and handles inserted or removed steps.
3. **Pair leftovers** inside each replaced block by a similarity score (same action type required; role 0.3 +
   name 0.3 + instruction text 0.2 + expected_state 0.2). A pair ≥ 0.6 is `changed`; the rest are `added` /
   `removed`. Greedy best-pair-first is fine at ~5 steps.
4. **Field changes** for each paired step, over the definition fields only: `action`, `target.role`, `target.name`,
   `expected_state`, `risk`, `instruction_text`.

Results:
- Self-heal (renamed button): `same, same, same, changed[target.name, instruction_text]`: exactly the story the UI
  should tell ("Step 4: button “Create Repository” → “Make repo”").
- Changed flow (extra confirm): `same, same, same, changed[expected_state], added[click button "Confirm"]`.
- Real runs of one task: the result is mostly `same` + `changed` (wording / expected_state), and `added` only where
  a plan really did add a step (the extra `navigate`). The removed/added pairs show up when a plan swaps
  `click link "New Repository"` for `navigate /repo/create`: same purpose, different action. That should honestly
  appear as a change, not be hidden.

**Change categories the UI needs** (so it can collapse noise)
- `behaviour`: step added / removed / reordered, `action.type`/`value`, `target.role`/`name`/`selector`. Always shown.
- `check`: `expected_state` changed. Shown, since it changes what "verified" means.
- `wording`: `instruction_text` only. Collapsed by default ("text updated").
- `risk`: risk level changed. Shown, with emphasis when it goes up.
- Evidence (`bbox`, `scroll`, `verification`, screenshots) is never part of the diff. The visual side-by-side comes
  from the two versions' screenshots, which the UI already has per step.

## Recommendation
1. **Compute the diff in the backend, once, when a version is created**, and store it as
   `workflow_versions.change_summary` (vs the parent version). Reasons: the backend has both step lists and owns the
   step format; Python's `difflib` gives the alignment for free; the heal code already knows *why* a step changed and
   can add that (`reason: "renamed: matched by form + id, score 0.86"`). The frontend only renders.
2. **Shape** (for the `WorkflowVersion` contract, Nachiketha's #114 renders it):
   ```json
   {"from_version": 1, "to_version": 2, "steps": [
     {"kind": "same", "old_seq": 1, "new_seq": 1},
     {"kind": "changed", "old_seq": 4, "new_seq": 4, "category": "behaviour",
      "fields": [{"field": "target.name", "from": "Create Repository", "to": "Make repo"},
                 {"field": "instruction_text", "from": "Click “Create Repository”.", "to": "Click “Make repo”."}]},
     {"kind": "added", "new_seq": 5, "category": "behaviour", "summary": "click button “Confirm”"}]}
   ```
   Masked values stay masked: the diff reads stored rows, which are already masked (`sensitive`).
3. For any two versions (not just parent → child), add `GET /workflows/{id}/versions/{a}/diff/{b}` later, computed on
   request with the same function. Not needed for the Phase 4 exit criteria.
4. Put the function in a pure module (e.g. `app/runs/step_diff.py` or next to the versions repository) with the two
   simulated cases plus one real noisy pair as unit tests.

No `architecture.md` change. The `change_summary` shape is a contract addition (in #108's contract PR).

## Open questions
- **Question for Nachiketha (#114):** is a stored `change_summary` per version enough for the diff view, or does the
  UI need any-to-any diffs right away?
- Should an `instruction_text`-only change between a heal and its parent be hidden entirely? It always comes with
  the rename, so "collapsed" seems right.
- Reordered steps show as `removed` + `added` today (LCS keeps order). A `moved` kind would need a second pass;
  no stored workflow has needed one yet.

## Links
- https://docs.python.org/3.12/library/difflib.html (`SequenceMatcher.get_opcodes`)
- https://www.rfc-editor.org/rfc/rfc6902
- `docs/research/phase-4-vishwas-workflow-versioning.md`, `docs/research/phase-4-vishwas-self-healing-locators.md`
- `docs/research/phase-1-nachiketha-frontend-sse-and-diff.md` (the plan-diff view this would sit next to)

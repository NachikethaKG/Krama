# Destructive-Action Classification

- **Phase:** 1
- **Researched by:** Nachiketha
- **Question(s):** Destructive-action classification: keyword denylist (delete, transfer, publish, …) plus an LLM classifier. Where do false positives come from (e.g. "Delete draft" on a harmless page)? Which Gitea actions should count as destructive?

## Findings

- **Keyword Denylist False Positives:**
  - A naive keyword denylist matching tokens such as `delete`, `drop`, `truncate`, `transfer`, `purge`, `revoke` creates extensive false positives on benign UI interactions (e.g., "Delete draft comment", "Clear search filter", "Remove label from issue", or "Dismiss notice") [verified locally].
- **Contextual Action-Entity Granularity:**
  - Destructive potential depends on the combination of `(action_verb, target_entity, scope)`. Clicking "Delete" on a repository settings page has irreversible system impact, whereas clicking "Delete" on an unsaved draft comment does not [verified locally].
- **Gitea Destructive Baseline Actions:**
  - Deleting a repository (`POST /repos/{owner}/{repo}/delete`) [verified: Gitea API docs, https://docs.gitea.com/api/1.22/].
  - Transferring repository ownership to another user or organization (`POST /repos/{owner}/{repo}/transfer`) [verified: Gitea API docs].
  - Deleting or force-pushing to protected git branches (`DELETE /repos/{owner}/{repo}/branches/{branch}`) [verified: Gitea API docs].
  - Revoking access tokens, deploy keys, or webhook integrations [verified: Gitea API docs].
  - Deleting user accounts or removing organization members [verified: Gitea API docs].
- **Two-Tier Detection Pipeline:**
  - Tier 1: Fast regex keyword filter flags candidate steps in <1ms.
  - Tier 2: Entity & URL context validator checks the current route (e.g., `/settings/delete`, `/settings/collaboration`) and target element ARIA role. If confirmed high-risk, the run state machine transitions to `paused` for human approval [verified: docs/phases/phase-1-verified-workflow.md].

## Recommendation

Implement a two-tier policy classifier:
1. Fast heuristic keyword check paired with target entity and page route validation (`(verb, entity, path)`).
2. Classify actions into `low`, `medium`, and `high` risk in `backend/app/policy/risk.py`.
3. High-risk actions must pause the run and require explicit human confirmation via the `/runs/{id}/confirm` API and frontend modal.
[No ADR required: conforms to safety rules in AGENTS.md §4 and Phase 1 roadmap].

## Open questions

- Should discarding uncommitted changes in a Web IDE count as medium or high risk? (To resolve during Together research in #45).

## Links

- [Gitea REST API Documentation (v1.22)](https://docs.gitea.com/api/1.22/)
- [Phase 1 Roadmap](file:///c:/Git/Krama/docs/phases/phase-1-verified-workflow.md)
- [Agent Guardrails](file:///c:/Git/Krama/docs/setup/agent-guardrails.md)

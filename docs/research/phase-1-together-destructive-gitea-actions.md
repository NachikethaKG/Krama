# Destructive Gitea actions: the first policy test set

- **Phase:** 1
- **Researched by:** Together. Prepared by Vishwas (experiments run by Claude Code on Vishwas's laptop); **decisions to confirm with Nachiketha**
- **Question(s):** Write the list of destructive Gitea actions together; it becomes the first policy test set.

> **Status: proposal.** This builds on Nachiketha's [phase-1-nachiketha-destructive-actions](phase-1-nachiketha-destructive-actions.md) (two-tier `(verb, entity, route)` classifier) and checks it against the real Gitea UI. The policy code is Nachiketha's (`policy/`); this note only supplies the evidence and the test cases.

## Findings
Method, 2026-10-11, local Gitea 1.22.6, signed in as `demo` [verified locally: scripts in [`assets/phase-1-together-policy-and-verification/`](assets/phase-1-together-policy-and-verification/)]:
1. `fixture.py` created a throwaway repo, `demo/policy-fixture`, with a branch, label, milestone, issue + comment, release and webhook. The wiki API returned 404, so the wiki wasn't covered.
2. `crawl.py` opened 21 pages (repo, repo settings, branches, releases, issue, labels, milestones, webhook, user settings, dashboard) with **`page.goto` only: nothing was clicked or submitted**. It listed every control whose label contains a risky verb (delete, remove, transfer, archive, private, close, lock, block, mirror, …), including hidden controls inside closed dialogs, with the form method and action they would submit. Raw output: `controls.json`.
3. `modals.py` listed every confirmation dialog's title, buttons and inputs. `dialog_aria.py` opened two delete dialogs **without confirming** (the branch still existed afterwards) to see what our agent's ARIA snapshot shows.

**1. The click that deletes is often just "Yes".** Gitea uses two kinds of confirmation [verified locally: `modals.py`]:

| Dialog title | Buttons | Typed confirmation |
|---|---|---|
| Delete This Repository | Cancel, **Delete Repository** | repo name |
| Transfer Ownership | Cancel, **Perform Transfer** | repo name + new owner |
| Delete Wiki Data | Cancel, **Delete Wiki Data** | repo name |
| Archive This Repo | No, **Yes** | — |
| Delete Branch | No, **Yes** | — |
| Delete Label / Delete Milestone / Remove Webhook / Delete this issue? | No, **Yes** | — |
| Lock conversation / Block a user | Cancel, **Lock** / **Block** | — |

A keyword check on the clicked element's name catches "Delete Repository" but **not "Yes"**, which is the actual delete for branches, labels, milestones, webhooks, issues and archiving.

**2. The dialogs have no `dialog` role.** After clicking `Delete Branch "feature-x"`, `get_by_role("dialog")` found **0** dialogs. The ARIA snapshot shows the open modal only as text followed by two buttons [verified locally: `dialog_aria.py`]:
```yaml
- text: Delete Branch feature-x
- paragraph: Deleting a branch is permanent. … it CANNOT be undone in most cases. Continue?
- button "No"
- button "Yes"
```
So the only context for "Yes" is the text just before it, and it sits **outside `main`**, so the observer's ARIA excerpt doesn't contain it (see [phase-1-together-verified-definition](phase-1-together-verified-definition.md)).

**3. Opening a dialog is harmless.** Clicking the opener changed nothing on the server: `feature-x` was still listed by the API afterwards. So pausing *at the opener* loses nothing and gives the human the clearest context ("Delete Branch feature-x").

**4. The verb list is noisy in both directions** [verified locally: `controls.json`]
- **False positives:**
  - `Cancel` and `No` (on every dialog)
  - `How do I mirror repositories?` (a docs link)
  - `Drop files or click here to upload.`
  - the dashboard filter link `Private`
  - `Create merge commit` (a merge-style option)
  - `Sign Out` (on every page, hidden in the user menu)
- **Missed by verbs, but risky:**
  - the generic `Yes`
  - the visibility **checkbox** `Make repository private` (a checkbox, not a button; it's saved by a generic "Update Settings")
  - `Add Push Mirror`: pushes the code to an external remote, i.e. sending data out
  - `Update Password`
- **Ambiguous names:** labels and milestones both have a bare `Delete` link. Only the page (`/labels` vs `/milestones`) says what is deleted, which supports Nachiketha's `(verb, entity, route)` idea.

**5. Not found in this Gitea:**
- account deletion (no "Delete Your Account" on `/user/settings/account` for this user/config)
- a "Delete File" control on the file view
- the wiki

These may depend on Gitea settings or permissions [unverified]. No tokens, SSH keys or org memberships existed, so token revoke, key delete and "leave organization" weren't seen. Add them when fixtures exist.

## Recommendation (proposal)
**Policy rules**, for Nachiketha's `policy/` to implement:
1. **Pause at the opener, not only at the confirm.** If a planned click opens a destructive dialog (`Delete …`, `Transfer Ownership`, `Archive Repo`, `Remove Webhook`, `Lock conversation`), classify that step as the destructive one and pause there.
2. **A generic confirm inherits the dialog's risk.** For `Yes`/`OK`/`Confirm`/`Continue`, look at the previous planned step and the text just before the button in the snapshot. Never treat "Yes" as low risk on its own.
3. **Typed confirmations are a strong signal.** If the plan fills a repo name into a confirmation textbox, the step is high risk.
4. **Context beats verbs:** use `(name, role, route)`. Bare `Delete` on `/labels` is "delete label"; `Private` as a dashboard link is a filter, but as a settings checkbox it's a visibility change.
5. **Also high risk** (missed by verbs): visibility changes, push mirrors (sending code out), password and security settings.
6. **Planner rule:** never plan `Sign Out` unless the task asks for it (it ends the run's own session).

**The test set**: [`gitea-policy-test-set.json`](assets/phase-1-together-policy-and-verification/gitea-policy-test-set.json), 30 cases from the real UI, each with page, role, exact name, kind (`opener`, `confirm`, `submit`, `toggle`, `benign`, `session`), proposed risk and why:
- **high (19):** delete repository, transfer, delete wiki, archive, visibility, push mirror, delete branch, release, webhook, label, milestone, comment, avatar (repo and user), update password, block user, and the generic `Yes`.
- **medium (5):** close issue, lock conversation, close milestone, rename branch, sign out.
- **low / false positives (6):** Cancel, No, the mirror docs link, the upload drop zone, the `Private` filter, Unwatch.

Two roles in the set (comment `Delete`, `Delete Release`) weren't checked and are marked in the file.

Use: every `high` case must pause, and no `low` case may pause. That checks both recall and false positives.

## Open questions (for the call)
- Should **every** delete be high, even an avatar? Proposal: yes, because AGENTS.md says deletes pause, and the cost is one confirmation.
- Is **archive** high or medium? Proposal: high. It is reversible, but it blocks all writes to the repo.
- Nachiketha's open question about discarding unsaved Web IDE changes: Gitea 1.22 has no Web IDE; the closest is "Cancel" while editing a file, which loses only unsaved text → low. To agree on the call.
- Add tokens, SSH keys and an organisation to the fixture, to cover revoke, delete-key and leave-org.

## Links
- [phase-1-nachiketha-destructive-actions](phase-1-nachiketha-destructive-actions.md)
- https://docs.gitea.com/api/1.22/ (the API used to create the fixture)
- AGENTS.md §4 (destructive actions pause for human confirmation)

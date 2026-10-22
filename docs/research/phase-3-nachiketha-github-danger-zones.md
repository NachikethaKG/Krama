# Danger Zones and Security-Sensitive Actions on GitHub

- **Phase:** 3
- **Researched by:** Nachiketha
- **Question(s):** Danger zones on GitHub: which GitHub UI actions are destructive or security-sensitive (Settings → Danger Zone, deploy keys, secrets, visibility changes, deleting branches)? Turn them into policy rules and tests.

## Findings

### 1. Repository Settings "Danger Zone"

GitHub groups irreversible, high-consequence administrative actions under the `#danger-zone` section on repository settings pages (`https://github.com/<owner>/<repo>/settings`) [verified locally]:

- **Repository Deletion:**
  - Action Form: `form[action$="/delete"]` or `form[action*="/settings/delete"]` [verified locally].
  - Trigger Button: Button with text `"Delete this repository"` [verified locally].
  - Multi-step Confirmation Modal: Dialog titled `"Delete <owner>/<repo>"`, requiring the user to type the full repository name or slug to confirm before the button `"I understand the consequences, delete this repository"` is enabled [verified locally].
  - Impact: Irreversible destruction of git history, pull requests, issues, releases, and settings.
- **Repository Visibility Changes:**
  - Trigger Button: Button with text `"Change visibility"` [verified locally].
  - Modal Options: Dialog options `"Change to public"` or `"Change to private"` [verified locally].
  - Confirmation Check: Modal requires typing `"I want to make this repository public/private"` [verified locally].
  - Impact: Making a private repository public risks leaking proprietary code or sensitive history.
- **Repository Transfer & Archiving:**
  - Transfer: Button `"Transfer"` / `form[action$="/transfer"]`, modal prompting for new owner username and typing the repository name [verified locally].
  - Archiving: Button `"Archive this repository"`, modal dialog marking repository read-only [verified locally].

### 2. Access Control, Deploy Keys, and Secrets Management

GitHub provides granular credential access pages that present substantial security risks if mutated by an automated agent [verified locally]:

- **Deploy Keys (`/<owner>/<repo>/settings/keys`):**
  - Creation: Button `"Add deploy key"`, form with fields for title, SSH key, and write-access checkbox [verified locally].
  - Deletion: Button `"Delete"` on existing keys, form `form[action*="/keys/"][action$="/delete"]` with confirmation prompt [verified locally].
  - Risk: Granting persistent SSH push/pull credentials without human review.
- **Actions Secrets & Environment Variables (`/<owner>/<repo>/settings/secrets/actions`):**
  - Creation / Update: Button `"New repository secret"`, input fields `input#secret_name`, `textarea#secret_value` [verified locally].
  - Deletion: Button `button[aria-label^="Delete secret"]` or form `form[action*="/secrets/actions/"][action$="/delete"]` [verified locally].
  - Note: While secret values cannot be read from the UI (they are write-only), overwriting or deleting an existing CI/CD secret causes immediate pipeline breakage [verified locally].
- **Collaborator Removal (`/<owner>/<repo>/settings/access`):**
  - Button `button[aria-label^="Remove "]`, action form `form[action$="/remove_member"]` or confirmation modal `"Remove collaborator"` [verified locally].
  - Risk: Revoking access for active maintainers or contributors.

### 3. Branch and Tag Deletion

Branch operations outside PR merges carry risk of losing unmerged work [verified locally]:

- **Branch Overview (`/<owner>/<repo>/branches` and `/branches/all`):**
  - **Scope Restriction (Consensus Alignment 2026-10-22):** The `/branches` route itself is **NOT** a danger zone.
    Viewing branches, listing active/stale/PR branches, and standard branch creation ("New branch" button and modal)
    are classified as `RiskLevel.LOW` to allow benchmark tasks like `github-create-branch` to execute without
    false-positive pauses.
  - **Delete Controls (Strictly `RiskLevel.HIGH`):** Trash icon button `button[aria-label="Delete branch"]`,
    `button[title="Delete branch"]`, deletion confirmation dialogs, or `form[action*="/branches/"] button[type="submit"]`
    trigger mandatory human confirmation [verified locally].
  - Default Branch Protection: GitHub prevents direct deletion of the repository default branch (`main` / `master`) from this list, but feature and release branches can be deleted with a single click [verified locally].
- **Branch Protection Rules (`/<owner>/<repo>/settings/branches`):**
  - Actions: Buttons `"Delete"` or `"Edit"` on branch protection rules (`form[action*="/branch_protection/"]`) [verified locally].
  - Risk: Weakening or deleting branch protection rules removes mandatory code reviews and CI checks.

### 4. Releases and Packages

- **Release Deletion (`/<owner>/<repo>/releases`):**
  - Delete Control: Button or link with text `"Delete"`, modal with text `"Are you sure you want to delete this release?"` [verified locally].
  - Risk: Removes compiled release assets, tags, and download history.

## Recommendation

Extend Krama's policy layer in `backend/app/policy/denylist.py` and `risk.py`:

1. **Add GitHub Danger-Zone Route & Selector Rules to `denylist.py`:**
   ```python
   # Settings routes that contain exclusively sensitive/destructive configuration
   GITHUB_DANGER_ROUTES: Final[tuple[re.Pattern[str], ...]] = (
       re.compile(r"^/[^/]+/[^/]+/settings/(danger-zone|keys|secrets|access|branches)", re.IGNORECASE),
   )

   # Destructive controls that elevate to RiskLevel.HIGH regardless of route
   # (includes branch deletion on /branches without flagging the entire page)
   GITHUB_DESTRUCTIVE_CONTROLS: Final[re.Pattern[str]] = re.compile(
       r"\b(delete this repository|change visibility|transfer ownership|archive this repository"
       r"|delete branch|remove collaborator|delete secret|add deploy key|delete release)\b",
       re.IGNORECASE,
   )
   ```
2. **Elevate to `RiskLevel.HIGH` in `risk.py`:**
   - Any proposed browser action targeting controls in the GitHub Danger Zone (`GITHUB_DANGER_ROUTES`) or matching `GITHUB_DESTRUCTIVE_CONTROLS` is automatically evaluated as `RiskLevel.HIGH`.
   - Branch listing, viewing, and branch creation ("New branch") on `/<owner>/<repo>/branches` remain `RiskLevel.LOW`.
   - Halts the execution pipeline and emits `run.paused` with structured risk details (`risk_level: "high"`, `reason: "github_danger_zone"`).
3. **Frontend Confirmation Modal:**
   - The user must explicitly inspect and confirm the high-risk action in `PolicyConfirmationModal` (`frontend/components/safety/`) before the agent is permitted to click or submit.
4. **Unit and Integration Tests:**
   - Add test fixtures in `backend/tests/policy/test_github_danger_zones.py` covering all danger zone selectors, modals, and route patterns. Ensure tests verify that creating a branch is `LOW` while deleting a branch is `HIGH`.

[No ADR required: directly implements AGENTS.md §4 mandatory destructive action policy].

## Open questions

- For automated benchmark suites (`benchmarks/`), should test repository cleanup be executed by the UI agent or by an out-of-band direct API script with a test token? (Vishwas's cleanup script should use the GitHub REST API directly to avoid triggering UI safety pause barriers).

## Links

- [GitHub Docs — Managing Repository Settings](https://docs.github.com/repositories/managing-your-repositorys-settings-and-features)
- [GitHub Docs — Setting Repository Visibility](https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [GitHub Docs — Managing Deploy Keys](https://docs.github.com/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
- [Krama AGENTS.md §4 Product-code Safety Rules](file:///c:/Git/Krama/AGENTS.md)

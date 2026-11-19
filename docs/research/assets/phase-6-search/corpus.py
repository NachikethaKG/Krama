"""Realistic workflow corpus for the #135 search spike: universal titles and step text ("your repository")."""

# (key, app, title, request, status, version_source, age_days, steps)
WORKFLOWS = [
    ("create_repo", "gitea", "Create a new repository", "create a repo called demo-repo on gitea", "verified", "initial", 3, [
        "Open the + menu at the top right.", "Click New Repository in the menu.", "Type the repository name.",
        "Check Initialize Repository to add .gitignore, License and README.", "Click Create Repository button to submit the form."]),
    ("add_collab_gitea", "gitea", "Add a collaborator to a repository", "add user bob as collaborator to krama-bench/demo", "verified", "initial", 10, [
        "Open your repository.", "Click Settings in the repository menu.", "Open the Collaborators tab.",
        "Type the user's name in the search box.", "Click Add Collaborator.", "Check the user now appears in the collaborators list."]),
    ("add_collab_github", "github", "Add a collaborator to a repository", "invite alice to my repo vishwas/site as collaborator", "verified", "heal", 40, [
        "Open your repository on GitHub.", "Click Settings.", "Click Collaborators in the Access section of the sidebar.",
        "Click Add people.", "Type the person's username, full name or email.", "Choose the person and click Add to repository.",
        "Check the invitation is listed as pending."]),
    ("create_issue", "gitea", "Create an issue", "open an issue titled Login broken", "verified", "initial", 5, [
        "Open your repository.", "Click the Issues tab.", "Click New Issue.", "Type a title for the issue.",
        "Write a description in the comment box.", "Click Create Issue."]),
    ("create_label", "gitea", "Create a label", "make a bug label in red", "verified", "initial", 8, [
        "Open your repository.", "Click the Issues tab.", "Click Labels.", "Click New Label.",
        "Type the label name, for example bug.", "Pick a color.", "Click Create Label."]),
    ("label_issue", "gitea", "Add a label to an issue", "tag issue 3 with bug", "verified", "initial", 12, [
        "Open your repository.", "Click the Issues tab.", "Open the issue.", "Click Labels in the right sidebar.",
        "Select the label, for example bug.", "Click outside the menu to apply it.", "Check the label is shown on the issue."]),
    ("branch_protection", "gitea", "Protect a branch", "protect main branch so nobody can push directly", "verified", "initial", 20, [
        "Open your repository.", "Click Settings.", "Open the Branches tab.", "Click Add New Rule.",
        "Type the branch name pattern, for example main.", "Select Disable Push.", "Click Save Rule."]),
    ("branch_protection_gh", "github", "Add a branch protection rule", "require PR reviews on main in vishwas/site", "outdated", "initial", 90, [
        "Open your repository on GitHub.", "Click Settings.", "Click Branches in the sidebar.", "Click Add classic branch protection rule.",
        "Type main as the branch name pattern.", "Check Require a pull request before merging.", "Click Create."]),
    ("webhook", "gitea", "Add a webhook", "add a webhook that posts to https://example.com/hook", "verified", "initial", 15, [
        "Open your repository.", "Click Settings.", "Open the Webhooks tab.", "Click Add Webhook and choose Gitea.",
        "Type the target URL.", "Choose which events trigger the webhook.", "Click Add Webhook."]),
    ("delete_repo", "gitea", "Delete a repository", "delete krama-bench/old-repo", "verified", "initial", 2, [
        "Open your repository.", "Click Settings.", "Scroll to the Danger Zone.", "Click Delete This Repository.",
        "Type the repository name to confirm.", "Click Delete Repository."]),
    ("visibility", "gitea", "Change repository visibility", "make my repo private", "verified", "heal", 30, [
        "Open your repository.", "Click Settings.", "Scroll to the Danger Zone.", "Click Change Repository Visibility.",
        "Check Make Repository Private.", "Confirm the change."]),
    ("visibility_gh", "github", "Change repository visibility", "make vishwas/site public", "verified", "initial", 25, [
        "Open your repository on GitHub.", "Click Settings.", "Scroll to the Danger Zone.", "Click Change visibility.",
        "Choose Change to private or Change to public.", "Read the warnings and click I want to change the visibility.",
        "Confirm the change."]),
    ("invite_org", "gitea", "Add a member to an organization team", "add bob to the owners team of krama-org", "verified", "initial", 18, [
        "Open your organization.", "Click Teams.", "Open the team, for example Owners.", "Type the user's name in the search box.",
        "Click Add Team Member.", "Check the member appears in the team."]),
    ("invite_org_gh", "github", "Invite a member to an organization", "invite carol to my-org", "outdated", "initial", 120, [
        "Open your organization on GitHub.", "Click People.", "Click Invite member.", "Type the person's username or email.",
        "Choose a role, for example Member.", "Click Send invitation."]),
    ("create_org", "gitea", "Create an organization", "create org krama-org", "verified", "initial", 7, [
        "Open the + menu at the top right.", "Click New Organization.", "Type the organization name.",
        "Choose the visibility.", "Click Create Organization."]),
    ("rename_repo", "gitea", "Rename a repository", "rename demo to demo-2", "verified", "initial", 9, [
        "Open your repository.", "Click Settings.", "Type the new name in the Repository Name field.", "Click Update Settings."]),
    ("transfer_repo", "gitea", "Transfer repository ownership", "move demo to krama-org", "verified", "initial", 33, [
        "Open your repository.", "Click Settings.", "Scroll to the Danger Zone.", "Click Transfer Ownership.",
        "Type the new owner's name.", "Type the repository name to confirm.", "Click Perform Transfer."]),
    ("ssh_key", "gitea", "Add an SSH key", "add my ssh public key", "verified", "initial", 11, [
        "Open the user menu at the top right.", "Click Settings.", "Open the SSH / GPG Keys tab.", "Click Add Key.",
        "Paste your public key into the Content box.", "Click Add Key."]),
    ("milestone", "gitea", "Create a milestone", "create milestone v1.0 due next friday", "verified", "initial", 14, [
        "Open your repository.", "Click the Issues tab.", "Click Milestones.", "Click New Milestone.",
        "Type a title and pick a due date.", "Click Create Milestone."]),
    ("close_issue", "gitea", "Close an issue", "close issue 4", "verified", "initial", 6, [
        "Open your repository.", "Click the Issues tab.", "Open the issue.", "Click Close Issue."]),
    ("assign_issue", "gitea", "Assign an issue to someone", "assign issue 2 to bob", "verified", "initial", 16, [
        "Open your repository.", "Click the Issues tab.", "Open the issue.", "Click Assignees in the right sidebar.",
        "Select the person.", "Check their avatar shows under Assignees."]),
    ("pr_create", "gitea", "Open a pull request", "open a PR from feature to main", "verified", "initial", 4, [
        "Open your repository.", "Click the Pull Requests tab.", "Click New Pull Request.",
        "Choose the base and compare branches.", "Type a title and description.", "Click Create Pull Request."]),
    ("create_branch", "gitea", "Create a branch", "create branch feature-x", "verified", "initial", 22, [
        "Open your repository.", "Click the branch menu above the file list.", "Type the new branch name.",
        "Click Create branch."]),
    ("release", "gitea", "Publish a release", "release v1.2.0", "verified", "initial", 28, [
        "Open your repository.", "Click Releases.", "Click New Release.", "Type the tag name, for example v1.0.",
        "Type a title and notes.", "Click Publish Release."]),
    ("wiki", "gitea", "Create a wiki page", "add a wiki page Getting Started", "verified", "initial", 35, [
        "Open your repository.", "Click the Wiki tab.", "Click New Page.", "Type the page title and content.", "Click Save Page."]),
    ("star_repo", "gitea", "Star a repository", "star gitea/tea", "verified", "initial", 50, [
        "Open the repository.", "Click Star at the top right."]),
    ("fork_repo", "github", "Fork a repository", "fork torvalds/linux", "verified", "initial", 45, [
        "Open the repository on GitHub.", "Click Fork.", "Choose an owner for the fork.", "Click Create fork."]),
    ("profile", "gitea", "Change your profile picture", "update my avatar", "verified", "initial", 60, [
        "Open the user menu at the top right.", "Click Settings.", "Find the Avatar section.",
        "Choose Use Custom Avatar and upload an image.", "Click Update Avatar."]),
    ("password", "gitea", "Change your password", "change my password", "verified", "initial", 70, [
        "Open the user menu at the top right.", "Click Settings.", "Open the Account tab.",
        "Type your current password and the new password twice.", "Click Update Password."]),
    ("deploy_key", "gitea", "Add a deploy key", "add a read-only deploy key to demo", "outdated", "initial", 100, [
        "Open your repository.", "Click Settings.", "Open the Deploy Keys tab.", "Click Add Deploy Key.",
        "Type a title and paste the public key.", "Click Add Deploy Key."]),
    ("archive_repo", "gitea", "Archive a repository", "archive old-repo", "verified", "initial", 13, [
        "Open your repository.", "Click Settings.", "Scroll to the Danger Zone.", "Click Archive This Repository.",
        "Type the repository name to confirm.", "Click Archive Repository."]),
    ("gh_token", "github", "Create a personal access token", "make a github token with repo scope", "verified", "initial", 21, [
        "Open your profile menu and click Settings.", "Click Developer settings.", "Click Personal access tokens, then Fine-grained tokens.",
        "Click Generate new token.", "Type a name and choose an expiry.", "Choose the repositories and permissions.", "Click Generate token."]),
]

# (query, set of relevant keys: a hit if any of them is in the top 3)
QUERIES = [
    ("how do I add a collaborator on GitHub?", {"add_collab_github"}),
    ("add colaborator", {"add_collab_gitea", "add_collab_github"}),
    ("make repo private", {"visibility", "visibility_gh"}),
    ("invite someone", {"add_collab_github", "invite_org_gh", "invite_org", "add_collab_gitea"}),
    ("delete a repository", {"delete_repo"}),
    ("protect main branch", {"branch_protection", "branch_protection_gh"}),
    ("webhook", {"webhook"}),
    ("open a new issue", {"create_issue"}),
    ("tag an issue as bug", {"label_issue"}),
    ("rename repo", {"rename_repo"}),
    ("ssh key", {"ssh_key", "deploy_key"}),
    ("give someone access to my repository", {"add_collab_gitea", "add_collab_github"}),
]

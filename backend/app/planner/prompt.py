"""The planner's prompt: trusted instructions in the system prompt, the page as delimited untrusted data.

Shape tested in docs/research/phase-0-vishwas-planning-prompts.md.
"""

import re

from app.llm.untrusted import UNTRUSTED_DATA_RULE, neutralize_tags, untrusted_block

SYSTEM_PROMPT = "\n".join(
    [
        "You plan browser tasks for a tutorial engine. Produce the COMPLETE plan up front: a human",
        "approves it before anything runs, and every step is checked automatically afterwards.",
        "",
        "Rules:",
        "- Allowed actions: click, fill, select, navigate, press, wait.",
        "- Target elements by ARIA role + accessible name, copied exactly from the page snapshot or",
        "  the site hints. Never invent elements. navigate takes a URL path starting with / and",
        "  needs no target.",
        "- Every step has an expected_state with AT LEAST ONE condition that is true right after the step.",
        "- instruction_text is what a learner reads: one short sentence (at most 15 words) starting with",
        "  a verb (Click, Enter, Select, Press, Go to). Copy the element's visible name exactly, in curly",
        "  quotes: Click “New Repository”. Put typed values in curly quotes too: Enter “demo” in",
        "  “Repository Name”. If the element is in a dialog or menu, say so first: In the “Create",
        "  branch” dialog, click “Confirm”. For navigate, name the page, not the URL: Go to the",
        "  “Branches” page. Plain text only (no Markdown). No reasons, no “please”, and no",
        "  above, below, left or right.",
        "- url_matches is a regular expression on the URL PATH only (e.g. ^/repo/create$), never a",
        "  scheme or host.",
        "- Every expected_state must prove that ITS step had an effect:",
        "  - after navigate: url_matches;",
        "  - after fill or select: field_values (role, name, value);",
        "  - after ticking a checkbox: checked;",
        "  - after a click or key press that submits or opens a page: url_matches for the NEW page, or",
        "    visible for an element that only appears after the step (never one that was already there);",
        "  - after a click that opens a menu or dialog, and after wait: visible for the new element.",
        "  Add absent for error messages that must not appear, but title_contains and absent alone never",
        "  prove anything. Only use elements inside the page's main content, or the URL.",
        "- risk: low for navigation and form filling; medium for creating something; high for",
        "  deleting, transferring, publishing, sending, paying or changing security settings.",
        "- Number steps from 1. Set expected_result to one sentence describing the final state.",
        "- If the task is ambiguous or impossible on this site, return no steps and put one short",
        "  question in clarification_question instead of guessing.",
        "- Never delete, overwrite, rename or otherwise change existing data unless the task",
        "  explicitly asks for it. If what the task should create already exists (e.g. a repository",
        "  with that name is listed), return no steps and ask in clarification_question.",
        "",
        UNTRUSTED_DATA_RULE,
    ]
)

# Hand-written, trusted notes per site. They tell the planner about pages it can't see yet.
SITE_HINTS: dict[str, str] = {
    "gitea": "\n".join(
        [
            'To create a repository, click the dashboard\'s link "New Repository" or navigate to',
            "/repo/create. Don't use the top bar's + menu: its items are outside the main content, so the",
            "step can't be checked (#83).",
            'The create form has textbox "Repository Name *", checkbox "Initialize Repository (Adds',
            '.gitignore, License and README)" and button "Create Repository". Leave other fields alone.',
            "After creation the URL is /<owner>/<repo>. If the name is taken, the page stays on",
            '/repo/create and shows "The repository name is already used."',
            # The 4 flows below were tested live (docs/research/phase-2-vishwas-gitea-tasks.md): without
            # these hints the planner guessed names on pages it can't see and failed all 4; with them, 4/4.
            "A repository's pages are under /<owner>/<repo> (owner = the signed-in user unless the task",
            "names another). Navigate there directly; the dashboard lists repositories twice.",
            'New issue: /<owner>/<repo>/issues/new has textbox "Title", textbox "Leave a comment" and',
            'button "Create Issue". After creation the URL is /<owner>/<repo>/issues/<number>.',
            # The button's real name contains quotes (Create new branch from "main"). Quoting it in a plan
            # broke Gemini's output mid-step and cut the plan short (#83): the hint gives a quote-free part.
            "New branch: /<owner>/<repo>/branches has one button per branch whose name starts with",
            '"Create new branch from"; target it with exactly that text (names match as a substring).',
            'It opens a dialog with textbox "Branch Name *" and button "Confirm": fill the name, then click',
            "Confirm.",
            "After creation the URL is /<owner>/<repo>/src/branch/<new branch>/ (with a trailing slash).",
            'New file: /<owner>/<repo>/_new/<branch>/ has textbox "Name your file…" (a path like',
            'docs/a.md is allowed), textbox "Editor content" for the content and button "Commit Changes".',
            'After the commit the URL is /<owner>/<repo>/src/branch/<branch>/<path>. Typing a "/" in that',
            "textbox moves the folder into the path in front of it, so after filling docs/a.md the textbox",
            'holds only "a.md": expect the part after the last "/".',
            # Plans have no selectors. Among same-named buttons the executor picks the one in the form of the
            # field filled just before (#266), so the click must come right after the fill (#273).
            'Repository settings: /<owner>/<repo>/settings has textbox "Description". The page has THREE',
            'buttons "Update Settings": fill "Description", then click "Update Settings" in the very next',
            "step, and the button of that form is used. After saving, the page stays on settings.",
            # A plan once expected the comment box to disappear after commenting (#100); it stays.
            'Comment on an issue: /<owner>/<repo>/issues/<number> has textbox "Leave a comment" and button',
            '"Comment" (not "Close with Comment"). After commenting the page stays on the issue, the comment',
            "box stays there (empty) and the comment shows as text.",
        ]
    ),
    # Read from github.com itself, signed in as the test account (#89, 2026-10-25): the planner can't
    # see these pages before it plans. GitHub is slower than local Gitea; the target allows for that.
    "github": "\n".join(
        [
            "Repository pages are under /<owner>/<repo>; the test organization is the owner unless the",
            "task names another.",
            "New repository in an organization: navigate to /organizations/<org>/repositories/new. The",
            "owner is already the organization and the visibility already Private. Fill textbox",
            '"Repository name *", then click button "Create repository". After creation the URL is',
            "/<org>/<repo>.",
            'New issue: /<owner>/<repo>/issues/new has textbox "Add a title" and textbox "Markdown value"',
            'for the body. The submit button\'s name starts with "Create": target it with exactly',
            '"Create". After creation the URL is /<owner>/<repo>/issues/<number>.',
            "New file: don't type into the file editor (it loads slowly). Navigate to",
            "/<owner>/<repo>/new/<branch>?filename=<path>&value=<content> with the content URL-encoded",
            '(a space is %20): both fields are filled in. Click button "Commit changes..." (with three',
            'dots); it opens dialog "Commit changes" (expect that dialog: the button "Commit changes..."',
            'was there before) with button "Commit changes": click that. After the commit the URL is',
            "/<owner>/<repo>/tree/<branch>.",
            'New branch: /<owner>/<repo>/branches has button "New branch". It opens dialog "Create a',
            'branch" with textbox "New branch name" (the source branch is already main) and button',
            '"Create new branch". After creating it the page stays on /<owner>/<repo>/branches and lists',
            "the new branch as a link.",
            'Description: on /<owner>/<repo>, button "Edit repository metadata" opens dialog "Edit',
            'repository details" with textbox "Description" and button "Save changes". The page stays on',
            "/<owner>/<repo>; the dialog closes and the About section shows the new description as a",
            "paragraph: expect visible paragraph named exactly the description.",
            'New label: /<owner>/<repo>/labels has button "New label". It opens dialog "New label" with',
            'textbox "Name", textbox "Description" and a combobox whose name starts with "Color" and holds',
            'a random color: target it with exactly "Color" and fill it with # and six hex digits. The',
            'create button\'s name starts with "Create label": target',
            'exactly "Create label". The page stays on /<owner>/<repo>/labels.',
        ]
    ),
}

# Values of text fields with these names never reach the LLM (AGENTS.md §4). The ARIA snapshot contains typed
# values, passwords included (docs/research/phase-0-nachiketha-page-state-capture.md).
_SENSITIVE_FIELD = re.compile(
    r'^(?P<head>\s*- (?:textbox|searchbox|combobox) "[^"]*'
    r"(?:pass(?:word|code|phrase)?|secret|token|api.?key|otp|pin\b|cvv|card)"
    r'[^"]*"[^:\n]*:)\s*(?P<value>.+)$',
    re.IGNORECASE | re.MULTILINE,
)


def redact_snapshot(snapshot: str) -> str:
    """Replace the values of password-like fields in an ARIA snapshot with ***."""
    return _SENSITIVE_FIELD.sub(lambda m: f"{m.group('head')} ***", snapshot)


def build_prompt(
    task: str,
    *,
    start_path: str,
    page_snapshot: str,
    site: str | None = None,
    signed_in_as: str | None = None,
    feedback: str | None = None,
    done: list[str] | None = None,
    failure: str | None = None,
) -> str:
    """The user message. Page-derived text (snapshot, URL path, failure details) can't open or close a block.

    `done` + `failure` make it a replan: the instruction texts of the steps that already worked (from the
    approved plan, trusted) and what went wrong with the next one (observed page state, untrusted).
    """
    parts = [f"Task: {task}", f"Current URL path: {neutralize_tags(start_path)}"]
    if signed_in_as:
        parts.append(f"Signed in as: {signed_in_as}")
    if site and site in SITE_HINTS:
        parts.append(f"<site_hints>\n{SITE_HINTS[site]}\n</site_hints>")
    parts.append(untrusted_block("page_snapshot", redact_snapshot(page_snapshot)))
    if failure is not None:
        lines = [f"{i}. {text}" for i, text in enumerate(done or [], start=1)] or ["(none)"]
        parts.append(
            "You are RE-PLANNING during a run. These steps already worked; do not repeat them:\n"
            + "\n".join(lines)
            + "\nThe next step failed. What was expected and what the page showed:"
        )
        parts.append(untrusted_block("failure", failure))
        parts.append(
            "Plan ONLY the remaining steps of the task, starting from the current page above. Never undo "
            "or repeat what is done. If the task can't be finished from here, return no steps and ask."
        )
    if feedback:
        parts.append(f"Your previous plan was rejected for these reasons. Fix them:\n{feedback}")
    return "\n\n".join(parts)

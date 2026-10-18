"""The text guide: a stored Verified Workflow as a numbered Markdown list with one screenshot per step (#79).

The step text is the workflow's `instruction_text` as is, the same text the tutorial shows. It contains page
labels (untrusted), so Markdown and HTML in it are escaped: a label can't add a link, an image or markup.
"""

import re
from collections.abc import Callable

from app.contracts_gen.workflow_schema import Workflow

# Characters that start Markdown/HTML syntax inside a line. Escaped with a backslash (CommonMark).
_MARKDOWN = re.compile(r"([\\`*_\[\]<>|!#~])")


def guide_markdown(workflow: Workflow, artifact_url: Callable[[str], str]) -> str:
    """`artifact_url` turns a stored screenshot key into the absolute URL the image is served at."""
    lines = [f"# {_escape(workflow.title)}", ""]
    meta = [f"{len(workflow.steps)} steps"]
    if workflow.target_url:
        site = _escape(workflow.target_app or "the site")
        meta.insert(0, f"Verified on {site} ({_escape(str(workflow.target_url))})")
    if workflow.created_at:
        meta.append(workflow.created_at.date().isoformat())
    lines += [f"_{' · '.join(meta)}_", ""]
    for number, step in enumerate(sorted(workflow.steps, key=lambda s: s.seq), start=1):
        text = _escape(step.instruction_text)
        lines += [f"{number}. {text}", ""]
        if step.screenshot_path:
            lines += [f"   ![Step {number}]({artifact_url(step.screenshot_path)})", ""]
    return "\n".join(lines).rstrip() + "\n"


def _escape(text: str) -> str:
    """One line of plain text, safe inside Markdown."""
    return _MARKDOWN.sub(r"\\\1", " ".join(text.split()))

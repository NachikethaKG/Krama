"""Tutorial step text from what actually ran: the executed action, the element's label and where it sat.

Deterministic, no LLM: on real Gitea steps this wrote the same text as Gemini and Llama 3.1, without their
mistakes (docs/research/phase-2-vishwas-instruction-text.md, ADR 0003). Plain text, not Markdown: the UI shows
step text as is and narration reads it aloud, so labels and values go in curly quotes, not bold:
Click “New Repository”.

Labels, section names and page titles come from the page: untrusted text, used only as quoted words.
"""

import re

from app.agent.context import ElementContext
from app.contracts_gen.common_schema import Action, Target

_MAX_WORDS = 8
_REQUIRED_MARK = re.compile(r"\s*\*$")
_TOGGLES = frozenset({"checkbox", "switch"})


def tutorial_text(
    action: Action,
    target: Target | None,
    context: ElementContext | None,
    *,
    page_title: str | None,
    sensitive: bool,
) -> str | None:
    """One imperative sentence for the step, or None when the facts aren't enough (keep the planner's text).

    `page_title` is the title of the page the step started on.
    """
    label = _clean(target.name) if target is not None else None
    match action.type:
        case "navigate" | "wait":
            # The planner names the page by what it is for ("Settings"); the page's own title can say
            # something else (Gitea's settings page is titled "Repository"), so its text is kept.
            return None
        case "press" if target is None:
            return f"Press {_q(action.value or '')}." if action.value else None
    if target is None or not label:
        return None  # selector-only target: no words a person would recognise
    role, value = target.role or "", action.value or ""
    match action.type:
        case "click" if role in _TOGGLES:
            sentence = f"select the {_q(label)} checkbox"
        case "click" if role == "radio":
            sentence = f"select {_q(label)}"
        case "click":
            sentence = f"click {_q(label)}"
        case "fill" if sensitive or not value:
            sentence = f"fill in {_q(label)}"
        case "fill" if "\n" in value or len(value.split()) > _MAX_WORDS:
            sentence = f"enter the text in {_q(label)}"
        case "fill":
            sentence = f"enter {_q(value)} in {_q(label)}"
        case "select":
            sentence = f"select {_q(value)} in {_q(label)}"
        case "press":
            sentence = f"press {_q(value)} in {_q(label)}"
        case _:
            return None
    return _capitalize(_where(context, label, page_title) + sentence) + "."


def _where(context: ElementContext | None, label: str, page_title: str | None) -> str:
    if context is None:
        return ""
    match context.container:
        case "dialog":
            return f"in the {_q(context.name)} dialog, " if context.name else "in the dialog, "
        case "menu":
            return "in the menu, "
        case "top_bar":
            return "in the top bar, "
        case "section":
            name = context.name or ""
            # A section that repeats the label ("Commit Changes" above the "Commit Changes" button) or the
            # page's own title ("New Repository" on the New Repository page) says nothing new.
            repeats = name.casefold() == label.casefold() or name.casefold() in (page_title or "").casefold()
            if not name or repeats:
                return ""
            return f"under {_q(name)}, "


def _clean(name: str | None) -> str | None:
    """The label as a person sees it: whitespace collapsed, the required-field star dropped."""
    if not name:
        return None
    return _REQUIRED_MARK.sub("", " ".join(name.split())) or None


def _q(text: str) -> str:
    """Curly-quote a page string. Its own quote marks are kept; only line breaks are flattened."""
    return f"“{' '.join(text.split())}”"


def _capitalize(sentence: str) -> str:
    return sentence[:1].upper() + sentence[1:]

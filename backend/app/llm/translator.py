"""The `Translator` port with an LLM (#422, decisions L4-L6; checked in
docs/research/assets/phase-6-languages).

Each UI label in a text becomes a token ([[Q1]], [[Q2]], ...) before the model sees it, so the model never
reads or rewrites the site's own words (and a label that tries to give orders never reaches it). The reply
must use every token exactly once; then the labels go back in, byte for byte. A text whose tokens don't come
back is None: the caller keeps that step in English. One request per tutorial.
"""

import json
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.llm.base import LLMError, LLMProvider
from app.llm.untrusted import UNTRUSTED_DATA_RULE, untrusted_block
from app.ports.translation import TranslationError, TranslationItem

LANGUAGES = {"hi": "Hindi", "kn": "Kannada", "de": "German", "es": "Spanish", "fr": "French"}
PROMPT_VERSION = "tokens-2"
_TOKEN = re.compile(r"\[\[Q(\d+)\]\]")

SYSTEM = "\n".join(
    [
        "You translate short software-tutorial sentences from English into {lang}.",
        "Rules:",
        "- Tokens like [[Q1]] stand for on-screen labels of the website. Copy every token exactly,",
        "  once each, and never translate, change, drop or add a token. Put each token where the label",
        "  belongs in a natural {lang} sentence.",
        "- Write the imperative, polite form a software tutorial uses. Keep it short. No explanations.",
        "- Keep product words such as repository, branch or README as {lang} software tutorials",
        "  usually write them.",
        "- Return one item per input item, with the same id.",
        UNTRUSTED_DATA_RULE,
    ]
)


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    text: str


class TranslationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[_Item]


def protect(text: str, labels: Sequence[str]) -> tuple[str, list[str]]:
    """`text` with each label it contains swapped for a token (longest first, so a label inside another is
    safe), and the labels in token order."""
    used: list[str] = []
    for label in sorted({lb for lb in labels if lb}, key=len, reverse=True):
        if label in text:
            used.append(label)
            text = text.replace(label, f"[[Q{len(used)}]]")
    return text, used


def restore(text: str, labels: Sequence[str]) -> str | None:
    """The labels back in, or None unless every token came back exactly once."""
    found = sorted(int(n) for n in _TOKEN.findall(text))
    if found != list(range(1, len(labels) + 1)):
        return None
    return _TOKEN.sub(lambda m: labels[int(m.group(1)) - 1], text)


class LLMTranslator:
    prompt_version = PROMPT_VERSION

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def translate(self, items: Sequence[TranslationItem], language: str) -> list[str | None]:
        if language not in LANGUAGES:
            raise TranslationError(f"no translation into {language!r}")
        if not items:
            return []
        prepared = [protect(it.text, it.labels) for it in items]
        lines = "\n".join(
            json.dumps({"id": i, "text": p}, ensure_ascii=False) for i, (p, _) in enumerate(prepared)
        )
        try:
            result = await self._provider.generate(
                system=SYSTEM.format(lang=LANGUAGES[language]),
                prompt="Translate each item's text.\n" + untrusted_block("items", lines),
                schema=TranslationBatch,
            )
        except LLMError as e:
            raise TranslationError(str(e)) from e
        by_id = {it.id: it.text for it in result.value.items}
        return [restore(by_id[i], labels) if i in by_id else None for i, (_, labels) in enumerate(prepared)]

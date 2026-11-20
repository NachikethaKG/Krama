"""Translator port (#421, #132): tutorial text from English into another language, UI labels untouched.

Decisions L4-L6 (docs/research/phase-6-decisions-alignment.md): the labels a step quotes are the site's own
words, so they must reach the learner byte for byte. Callers pass them as `labels`; a translator returns None
for a text whose labels didn't survive, and the caller keeps that step in English. Never a half-translated
step.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from app.ports.models import _Model


class TranslationItem(_Model):
    """One text to translate, with the labels inside it that must come back exactly as given."""

    text: str
    labels: tuple[str, ...] = Field(default=())


class TranslationError(Exception):
    """The translator couldn't answer at all (quota, network, a reply that isn't the schema)."""


class Translator(Protocol):
    prompt_version: str
    """Changes whenever the prompt does, so cached translations from an older prompt aren't reused."""

    async def translate(self, items: Sequence[TranslationItem], language: str) -> list[str | None]:
        """One result per item, in order: the text in `language`, or None when its labels didn't survive.

        Raises TranslationError when nothing came back."""
        ...


class FakeTranslator:
    """Tests and mock mode: "[hi] Click “New”." — labels kept, no LLM."""

    prompt_version = "fake-1"

    def __init__(self, broken: Sequence[int] = ()) -> None:
        self.calls: list[tuple[str, int]] = []
        self._broken = set(broken)

    async def translate(self, items: Sequence[TranslationItem], language: str) -> list[str | None]:
        self.calls.append((language, len(items)))
        return [None if i in self._broken else f"[{language}] {it.text}" for i, it in enumerate(items)]

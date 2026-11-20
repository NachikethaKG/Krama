"""Tutorials in other languages (#422, #132; decisions L4-L6).

A workflow version's title and step texts are translated once per language, on first request, in the
background, and every single text is cached by (sha256, language, prompt version), so a new version only
translates what changed. UI labels stay byte for byte the site's own: the quoted ones (“New repository”), and
for older texts that don't quote them, the step's target name. A step whose labels didn't survive keeps its
English text.
"""

import asyncio
import hashlib
import logging
import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts_gen.workflow_schema import Translation, Workflow
from app.db import TranslationCacheRow, TranslationRow, WorkflowRow, WorkflowStepRow
from app.ports.translation import TranslationError, TranslationItem, Translator

logger = logging.getLogger(__name__)

_QUOTED = re.compile(r"“[^”]*”")


def labels_of(text: str, target_name: str | None) -> tuple[str, ...]:
    """The UI labels inside a step text: its quoted labels, plus the target's name if it appears unquoted."""
    labels = _QUOTED.findall(text)
    if target_name and target_name in text and not any(target_name in lb for lb in labels):
        labels.append(target_name)
    return tuple(labels)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TranslationService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], translator: Translator) -> None:
        self._sessions = sessions
        self._translator = translator
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._failure_shown: set[UUID] = set()
        """Failed translations someone was told about: the next request tries again."""

    async def get(self, workflow: WorkflowRow, language: str) -> Translation:
        """The translation of the workflow's current version: ready, failed, or translating (then started in
        the background if it wasn't). A failure is reported once; the request after that starts it again."""
        if language == "en":
            return _original(workflow)
        assert workflow.current_version_id is not None
        async with self._sessions.begin() as s:
            row = await s.scalar(
                select(TranslationRow).where(
                    TranslationRow.version_id == workflow.current_version_id,
                    TranslationRow.language == language,
                )
            )
            if row is None:
                row = TranslationRow(
                    workflow_id=workflow.id, version_id=workflow.current_version_id, language=language
                )
                s.add(row)
                await s.flush()
            elif row.status == "failed" and row.id in self._failure_shown:
                self._failure_shown.discard(row.id)
                row.status, row.error = "translating", None
            elif row.status == "failed":
                self._failure_shown.add(row.id)  # report it once; the next request retries
            row_id, status = row.id, row.status
            out = _view(workflow, row)
        if status == "translating" and row_id not in self._tasks:
            task = asyncio.create_task(self._run(row_id), name=f"translate-{row_id}")
            self._tasks[row_id] = task
            task.add_done_callback(lambda _t: self._tasks.pop(row_id, None))
        return out

    async def wait(self, workflow: WorkflowRow, language: str) -> Translation:
        """The translation, made now if it isn't ready (the export job needs the text before rendering)."""
        out = await self.get(workflow, language)
        if out.status != "translating":
            return out
        assert workflow.current_version_id is not None
        async with self._sessions() as s:
            row_id = await s.scalar(
                select(TranslationRow.id).where(
                    TranslationRow.version_id == workflow.current_version_id,
                    TranslationRow.language == language,
                )
            )
        task = self._tasks.get(row_id) if row_id else None
        if task is not None:
            await asyncio.shield(task)
        elif row_id is not None:
            await self._run(row_id)
        return await self.get(workflow, language)

    async def localize(self, workflow: Workflow, language: str) -> Workflow:
        """The contract Workflow with its title and step texts in `language` (the export job, #428)."""
        async with self._sessions() as s:
            row = await s.get(WorkflowRow, workflow.id)
        if row is None or language == "en":
            return workflow
        translation = await self.wait(row, language)
        if translation.status != "ready":
            raise TranslationError(translation.error or "the translation failed")
        texts = {st.step_seq: st.text for st in translation.steps}
        steps = [
            st.model_copy(update={"instruction_text": texts.get(st.seq, st.instruction_text)})
            for st in workflow.steps
        ]
        return workflow.model_copy(update={"title": translation.title or workflow.title, "steps": steps})

    async def _run(self, row_id: UUID) -> None:
        async with self._sessions() as s:
            row = await s.get(TranslationRow, row_id)
            if row is None:
                return
            workflow = await s.get(WorkflowRow, row.workflow_id)
            steps = list(
                await s.scalars(
                    select(WorkflowStepRow)
                    .where(WorkflowStepRow.version_id == row.version_id)
                    .order_by(WorkflowStepRow.seq)
                )
            )
            language, title = row.language, workflow.title if workflow is not None else ""
        items = [TranslationItem(text=title)] + [
            TranslationItem(
                text=st.instruction_text, labels=labels_of(st.instruction_text, (st.target or {}).get("name"))
            )
            for st in steps
        ]
        try:
            results = await self._translate(items, language)
        except TranslationError as e:
            logger.info("translation %s failed: %s", row_id, e)
            await self._finish(row_id, status="failed", error=str(e))
            return
        except Exception:
            logger.exception("translation %s crashed", row_id)
            await self._finish(row_id, status="failed", error="internal error")
            return
        translated_steps = [
            {
                "step_seq": st.seq,
                "text": text if text is not None else st.instruction_text,
                "translated": text is not None,
            }
            for st, text in zip(steps, results[1:], strict=True)
        ]
        await self._finish(row_id, status="ready", title=results[0] or title, steps=translated_steps)

    async def _translate(self, items: Sequence[TranslationItem], language: str) -> list[str | None]:
        """Cached texts from the cache, the rest in one request; new results go into the cache."""
        version = self._translator.prompt_version
        shas = [_sha(it.text) for it in items]
        async with self._sessions() as s:
            cached = {
                r.text_sha: r.text
                for r in await s.scalars(
                    select(TranslationCacheRow).where(
                        TranslationCacheRow.text_sha.in_(shas),
                        TranslationCacheRow.language == language,
                        TranslationCacheRow.prompt_version == version,
                    )
                )
            }
        todo = [i for i, sha in enumerate(shas) if sha not in cached and items[i].text]
        fresh = await self._translator.translate([items[i] for i in todo], language) if todo else []
        results: list[str | None] = [cached.get(sha) for sha in shas]
        async with self._sessions.begin() as s:
            for i, text in zip(todo, fresh, strict=True):
                results[i] = text
                if (
                    text is not None
                    and await s.get(TranslationCacheRow, (shas[i], language, version)) is None
                ):
                    s.add(
                        TranslationCacheRow(
                            text_sha=shas[i], language=language, prompt_version=version, text=text
                        )
                    )
        return [r if r is not None or items[i].text else "" for i, r in enumerate(results)]

    async def _finish(self, row_id: UUID, **values: Any) -> None:
        async with self._sessions.begin() as s:
            row = await s.get(TranslationRow, row_id)
            if row is not None:
                for k, v in values.items():
                    setattr(row, k, v)


def _original(workflow: WorkflowRow) -> Translation:
    return Translation.model_validate(
        {
            "workflow_id": workflow.id,
            "revision": workflow.revision,
            "language": "en",
            "status": "ready",
            "title": workflow.title,
            "steps": [{"step_seq": st.seq, "text": st.instruction_text} for st in workflow.steps],
        }
    )


def _view(workflow: WorkflowRow, row: TranslationRow) -> Translation:
    return Translation.model_validate(
        {
            "workflow_id": workflow.id,
            "revision": workflow.revision,
            "language": row.language,
            "status": row.status,
            "title": row.title,
            "steps": row.steps or [],
            "error": row.error,
        }
    )

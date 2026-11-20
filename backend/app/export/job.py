"""The export job (#126, docs/phases/phase-5-video-export.md).

Runs in the arq worker on queue `krama:exports`, one at a time, no retry.
Flow (decision D14 in docs/research/phase-5-decisions-alignment.md):
1. `ExportStore.load(export_id)`: check stale status (worker stop -> fail as interrupted).
2. Mark rendering (progress 0).
3. Generate narration clips via `Narrator` (progress 10).
4. Drive the Remotion renderer with progress events (progress 10-98).
5. Store the MP4 at `exports/<id>.mp4` and `.vtt` at `exports/<id>.vtt` via `ArtifactFiles.put_file`.
6. Mark ready (progress 100).
"""

import asyncio
import contextlib
import logging
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from app.contracts_gen.export_schema import ExportErrorCode
from app.contracts_gen.step_schema import Step
from app.contracts_gen.workflow_schema import Workflow
from app.ports.artifacts import ArtifactFiles
from app.ports.exports import ExportNotFoundError, ExportStateError, ExportStore
from app.ports.narration import NarrationError, NarrationLine, Narrator, plan_scenes
from app.runs.exports import DbExportStore
from app.tts import get_narrator

from .renderer import RemotionRenderer, RenderError, VideoRenderer

type Localize = Callable[[Workflow, str], Awaitable[Workflow]]
"""The workflow with its title and step texts in a language (TranslationService.localize, #422)."""

logger = logging.getLogger(__name__)

type Ctx = dict[str, Any]


async def render_export(
    export_id: UUID,
    *,
    store: ExportStore,
    files: ArtifactFiles,
    narrator: Narrator,
    renderer: VideoRenderer | None = None,
    localize: Localize | None = None,
    narrator_for: Callable[[str], Narrator] | None = None,
) -> str:
    """Executes the export pipeline for one export ID. An export in another language (#428) gets its texts
    from `localize` and its voice from `narrator_for`; English uses `narrator` and the texts as stored."""
    job_input = await store.load(export_id)
    export = job_input.export
    workflow = job_input.workflow
    language = export.language or "en"

    if export.status == "rendering":
        # A worker died while rendering this export
        await store.mark_failed(export_id, "interrupted", "Export was interrupted by a worker stop")
        return "interrupted"

    if export.status != "queued":
        return export.status

    await store.mark_rendering(export_id, 0)

    if language != "en":
        if localize is None:
            await store.mark_failed(export_id, "internal", f"No translation into {language} on this server")
            return "internal"
        try:
            workflow = await localize(workflow, language)
        except Exception as e:
            logger.warning("Export %s translation failed: %s", export_id, e)
            await store.mark_failed(export_id, "internal", f"The {language} translation failed: {e}")
            return "internal"
        if narrator_for is not None:
            narrator = narrator_for(language)

    # 1. Spoken narration per step (Decision D3-D5)
    lines = [
        NarrationLine(step_seq=s.seq, text=s.instruction_text)
        for s in sorted(workflow.steps, key=lambda s: s.seq)
        if s.instruction_text
    ]

    try:
        manifest = await narrator.narrate(lines)
    except NarrationError as e:
        logger.warning("Export %s narration failed: %s", export_id, e)
        await store.mark_failed(export_id, "narration_failed", f"Narration failed: {e}")
        return "narration_failed"
    except Exception as e:
        logger.exception("Export %s narration crashed", export_id)
        await store.mark_failed(export_id, "narration_failed", f"Narration failed: {e}")
        return "narration_failed"

    await store.mark_rendering(export_id, 10)

    # 2. Collect local screenshots and audio files
    screenshots: dict[int, str] = {}
    for s in workflow.steps:
        for key in _scene_screenshots(s):
            try:
                shot_path = await files.local_path(key)
                if await asyncio.to_thread(shot_path.is_file):
                    screenshots[s.seq] = str(shot_path)
                    break
            except Exception:
                logger.debug("Screenshot %s not found locally for step %d", key, s.seq)

    audio_urls: dict[int, str] = {}
    for clip in manifest.clips:
        try:
            audio_path = await files.local_path(clip.audio_key)
            if await asyncio.to_thread(audio_path.is_file):
                audio_urls[clip.step_seq] = str(audio_path)
        except Exception:
            logger.debug("Audio %s not found locally for step %d", clip.audio_key, clip.step_seq)

    # 3. Video rendering
    rend = renderer or RemotionRenderer()
    with tempfile.TemporaryDirectory(prefix="krama-export-job-") as tmp_dir:
        tmp = Path(tmp_dir)
        tmp_mp4 = tmp / f"{export_id}.mp4"
        tmp_vtt = tmp / f"{export_id}.vtt"
        tmp_meta = tmp / f"{export_id}.txt"

        async def on_progress(p: int) -> None:
            scaled = min(98, 10 + int(p * 0.88))
            await store.mark_rendering(export_id, scaled)

        # Scene lengths follow the narration (D4): max(recorded action, lead-in + clip + hold), whole frames.
        actions = {
            s.seq: max(0, s.end_ms - s.start_ms)
            for s in workflow.steps
            if s.start_ms is not None and s.end_ms is not None
        }
        scenes = plan_scenes(manifest, actions)
        # Outro (D9): "Verified on <site>, <date of the version's run>".
        site = urlparse(str(workflow.target_url or "")).hostname or workflow.target_app or "git.local"
        when = workflow.updated_at or workflow.created_at
        verified = when.date().isoformat() if when else None
        try:
            result = await rend.render(
                output_path=tmp_mp4,
                preset=export.preset,
                workflow=workflow,
                manifest=manifest,
                screenshots=screenshots,
                audio_urls=audio_urls,
                vtt_path=tmp_vtt,
                metadata_path=tmp_meta,
                site=site,
                verified_date=verified,
                language=language,
                scenes=scenes,
                on_progress=on_progress,
            )
        except TimeoutError:
            logger.warning("Export %s render timed out", export_id)
            await store.mark_failed(export_id, "timeout", "Video rendering timed out")
            return "timeout"
        except RenderError as e:
            logger.warning("Export %s render failed: %s", export_id, e)
            await store.mark_failed(export_id, "render_failed", str(e))
            return "render_failed"
        except Exception as e:
            logger.exception("Export %s render crashed", export_id)
            await store.mark_failed(export_id, "render_failed", f"Rendering failed: {e}")
            return "render_failed"

        # 4. Store artifacts
        try:
            video_ref = await files.put_file(f"exports/{export_id}.mp4", tmp_mp4, "video/mp4")
            captions_ref = None
            has_vtt = await asyncio.to_thread(lambda: tmp_vtt.is_file() and tmp_vtt.stat().st_size > 0)
            if has_vtt:
                captions_ref = await files.put_file(f"exports/{export_id}.vtt", tmp_vtt, "text/vtt")
        except Exception as e:
            logger.exception("Export %s artifact storage failed", export_id)
            await store.mark_failed(export_id, "storage_failed", f"Failed to store video: {e}")
            return "storage_failed"

        # 5. Mark ready
        duration_ms = result.duration_ms or int(export.duration_ms or 0)
        await store.mark_ready(
            export_id,
            video=video_ref,
            captions=captions_ref,
            duration_ms=duration_ms,
        )
        return "ready"


async def run_export(
    export_id: UUID,
    *,
    store: ExportStore,
    files: ArtifactFiles,
    narrator: Narrator,
    renderer: VideoRenderer | None = None,
    timeout_s: float,
    localize: Localize | None = None,
    narrator_for: Callable[[str], Narrator] | None = None,
) -> str:
    """`render_export` within EXPORT_TIMEOUT_SECONDS. Whatever happens, the export doesn't stay `rendering`:
    a timeout fails it as `timeout`, a cancel (worker stop) as `interrupted`, a crash as `internal`."""
    try:
        return await asyncio.wait_for(
            render_export(
                export_id,
                store=store,
                files=files,
                narrator=narrator,
                renderer=renderer,
                localize=localize,
                narrator_for=narrator_for,
            ),
            timeout=timeout_s,
        )
    except TimeoutError:
        await _fail_if_running(store, export_id, "timeout", f"The export took longer than {timeout_s:g} s.")
        return "timeout"
    except asyncio.CancelledError:
        await _fail_if_running(store, export_id, "interrupted", "The export was stopped. Export again.")
        raise
    except Exception:
        logger.exception("Export %s crashed", export_id)
        await _fail_if_running(store, export_id, "internal", "The export failed unexpectedly.")
        return "internal"


_SHOW_BEFORE = frozenset({"click", "select", "press"})


def _scene_screenshots(step: Step) -> list[str]:
    """The screenshots a step's scene can use, best first (#388).

    A click, select or key press shows the page right before the action, with the target in view: the
    step's own screenshot is taken after it, often on the next page, where the element is gone and the box
    and scroll measured before the action point at nothing. A fill shows the page after typing (the value is
    visible); a navigate shows the page reached. Older steps have only the after-screenshot.
    """
    before = step.before_state.screenshot_path if step.before_state is not None else None
    after = step.screenshot_path
    keys = [before, after] if step.action.type in _SHOW_BEFORE else [after]
    return [k for k in keys if k]


async def _fail_if_running(store: ExportStore, export_id: UUID, code: ExportErrorCode, message: str) -> None:
    with contextlib.suppress(ExportStateError, ExportNotFoundError):  # already finished, or gone
        await store.mark_failed(export_id, code, message)


async def export_job(ctx: Ctx, export_id: str) -> str:
    """The arq job on queue `krama:exports` (one at a time, no retry; see app/worker.py)."""
    eid = UUID(export_id)
    store: ExportStore = ctx.get("export_store") or DbExportStore(ctx["sessions"])
    files: ArtifactFiles = ctx["files"]
    narrator: Narrator = ctx.get("narrator") or get_narrator()
    renderer: VideoRenderer | None = ctx.get("video_renderer")
    timeout_s: float = ctx.get("export_timeout_s", 1800.0)
    return await run_export(
        eid,
        store=store,
        files=files,
        narrator=narrator,
        renderer=renderer,
        timeout_s=timeout_s,
        localize=ctx.get("localize"),
        narrator_for=ctx.get("narrator_for", get_narrator),
    )

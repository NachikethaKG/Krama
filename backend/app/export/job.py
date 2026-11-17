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
import logging
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from app.ports.artifacts import ArtifactFiles
from app.ports.exports import ExportStore
from app.ports.narration import NarrationError, NarrationLine, Narrator
from app.runs.exports import DbExportStore
from app.tts import get_narrator

from .renderer import RemotionRenderer, RenderError, VideoRenderer

logger = logging.getLogger(__name__)

type Ctx = dict[str, Any]


async def render_export(
    export_id: UUID,
    *,
    store: ExportStore,
    files: ArtifactFiles,
    narrator: Narrator,
    renderer: VideoRenderer | None = None,
) -> str:
    """Executes the export pipeline for one export ID."""
    job_input = await store.load(export_id)
    export = job_input.export
    workflow = job_input.workflow

    if export.status == "rendering":
        # A worker died while rendering this export
        await store.mark_failed(export_id, "interrupted", "Export was interrupted by a worker stop")
        return "interrupted"

    if export.status != "queued":
        return export.status

    await store.mark_rendering(export_id, 0)

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
        if s.screenshot_path:
            try:
                shot_path = await files.local_path(s.screenshot_path)
                if await asyncio.to_thread(shot_path.is_file):
                    screenshots[s.seq] = str(shot_path)
            except Exception:
                logger.debug("Screenshot %s not found locally for step %d", s.screenshot_path, s.seq)

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

        site = workflow.target_app or "git.local"
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


async def export_job(ctx: Ctx, export_id: str) -> str:
    """The arq job on queue `krama:exports`."""
    eid = UUID(export_id)
    store: ExportStore = ctx.get("export_store") or DbExportStore(ctx["sessions"])
    files: ArtifactFiles = ctx["files"]
    narrator: Narrator = ctx.get("narrator") or get_narrator()
    renderer: VideoRenderer | None = ctx.get("video_renderer")

    return await render_export(eid, store=store, files=files, narrator=narrator, renderer=renderer)

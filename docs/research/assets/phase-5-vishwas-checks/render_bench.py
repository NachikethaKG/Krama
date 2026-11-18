"""Phase 5 gate: render time per preset on this laptop (real workflow, real Remotion, cached Piper narration).

Usage (from backend/, after `just backend tts-setup` and `pnpm install`; Docker up; on mains power):
    uv run --with psutil python -X utf8 ../docs/research/assets/phase-5-vishwas-checks/render_bench.py <workflow_id> 2
<workflow_id>: a stored workflow with screenshots (e.g. the 6-step GitHub "create label" one).
Prints one JSON line per render: preset, video seconds, wall seconds, fps, peak RSS of the renderer tree (MB).
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from uuid import UUID

import psutil

from app.config import get_settings
from app.api.convert import workflow_version_out
from app.db import TaskRow, WorkflowRow, WorkflowStepRow, WorkflowVersionRow, create_engine, create_sessionmaker
from app.export.renderer import RemotionRenderer
from app.ports.narration import NarrationLine, plan_scenes
from app.storage import LocalFsStore
from app.tts import get_narrator
from sqlalchemy import select


def tree_rss(root: psutil.Process) -> int:
    total = 0
    for p in [root, *root.children(recursive=True)]:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


async def main(workflow_id: UUID, runs: int) -> None:
    s = get_settings()
    engine = create_engine(s.database_url)
    sessions = create_sessionmaker(engine)
    async with sessions() as db:
        w = await db.get(WorkflowRow, workflow_id)
        v = await db.get(WorkflowVersionRow, w.current_version_id)
        steps = (await db.scalars(select(WorkflowStepRow).where(WorkflowStepRow.version_id == v.id).order_by(WorkflowStepRow.seq))).all()
        task = await db.get(TaskRow, w.task_id)
        wf = workflow_version_out(w, v, steps, task.prompt if task else None)
    await engine.dispose()
    files = LocalFsStore(s.artifacts_dir)
    manifest = await get_narrator().narrate([NarrationLine(step_seq=st.seq, text=st.instruction_text) for st in wf.steps])
    actions = {st.seq: st.end_ms - st.start_ms for st in wf.steps if st.start_ms is not None and st.end_ms is not None}
    scenes = plan_scenes(manifest, actions)
    shots = {st.seq: str(await files.local_path(st.screenshot_path)) for st in wf.steps if st.screenshot_path}
    audio = {c.step_seq: str(await files.local_path(c.audio_key)) for c in manifest.clips}
    me = psutil.Process(os.getpid())
    for preset in ("landscape", "portrait"):
        for _ in range(runs):
            peak = [0]
            stop = threading.Event()

            def sample() -> None:
                while not stop.is_set():
                    peak[0] = max(peak[0], tree_rss(me) - me.memory_info().rss)
                    time.sleep(0.25)

            t = threading.Thread(target=sample, daemon=True)
            t.start()
            with tempfile.TemporaryDirectory() as d:
                start = time.perf_counter()
                r = await RemotionRenderer().render(
                    output_path=Path(d) / "o.mp4", preset=preset, workflow=wf, manifest=manifest, screenshots=shots,
                    audio_urls=audio, site="github.com", scenes=scenes, timeout_s=900,
                )
                wall = time.perf_counter() - start
            stop.set()
            t.join()
            frames = round(r.duration_ms / 1000 * 30)
            print(json.dumps({"preset": preset, "video_s": round(r.duration_ms / 1000, 1), "wall_s": round(wall, 1),
                              "fps": round(frames / wall, 1), "peak_renderer_mb": round(peak[0] / 1e6)}), flush=True)


if __name__ == "__main__":
    asyncio.run(main(UUID(sys.argv[1]), int(sys.argv[2])))

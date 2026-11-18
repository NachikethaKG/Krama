"""Remotion video renderer wrapper (#126).

Spawns the `@krama/video-exporter` CLI via Node.js on CPU, streams progress events,
and produces the rendered MP4, WebVTT captions, and FFmpeg chapter metadata.
"""

import asyncio
import contextlib
import json
import logging
import os
import shutil
import tempfile
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.contracts_gen.tutorial_spec_schema import TutorialSpec
from app.contracts_gen.workflow_schema import Workflow
from app.ports.narration import NarrationManifest, SceneTiming

logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """The video renderer exited with an error or wrote corrupted output."""


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    duration_ms: int
    vtt_path: Path | None = None
    metadata_path: Path | None = None


class VideoRenderer(Protocol):
    """Protocol for driving video rendering."""

    async def render(
        self,
        *,
        output_path: Path,
        preset: str = "landscape",
        workflow: Workflow | None = None,
        spec: TutorialSpec | None = None,
        manifest: NarrationManifest | None = None,
        screenshots: dict[int, str] | None = None,
        audio_urls: dict[int, str] | None = None,
        vtt_path: Path | None = None,
        metadata_path: Path | None = None,
        site: str = "git.local",
        verified_date: str | None = None,
        scenes: Sequence[SceneTiming] | None = None,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
        timeout_s: float = 600.0,
    ) -> RenderResult: ...


class RemotionRenderer(VideoRenderer):
    """Drives the Remotion `@krama/video-exporter` CLI subprocess."""

    def __init__(
        self,
        package_dir: Path | None = None,
        *,
        node_path: str | None = None,
        concurrency: int = 4,
    ) -> None:
        self.package_dir = package_dir or (
            Path(__file__).resolve().parents[3] / "packages" / "video-exporter"
        )
        self.node_path = node_path or shutil.which("node") or "node"
        self.concurrency = concurrency

    async def render(
        self,
        *,
        output_path: Path,
        preset: str = "landscape",
        workflow: Workflow | None = None,
        spec: TutorialSpec | None = None,
        manifest: NarrationManifest | None = None,
        screenshots: dict[int, str] | None = None,
        audio_urls: dict[int, str] | None = None,
        vtt_path: Path | None = None,
        metadata_path: Path | None = None,
        site: str = "git.local",
        verified_date: str | None = None,
        scenes: Sequence[SceneTiming] | None = None,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
        timeout_s: float = 600.0,
    ) -> RenderResult:
        if workflow is None and spec is None:
            raise ValueError("Either workflow or spec must be provided")

        await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="krama-remotion-") as tmp_dir:
            tmp = Path(tmp_dir)
            cmd: list[str] = self._build_base_command()

            if spec is not None:
                spec_path = tmp / "spec.json"
                spec_data = spec.model_dump_json(exclude_none=True)
                await asyncio.to_thread(spec_path.write_text, spec_data, encoding="utf-8")
                cmd.extend(["--spec", str(spec_path)])
            elif workflow is not None:
                wf_path = tmp / "workflow.json"
                wf_data = workflow.model_dump_json(exclude_none=True)
                await asyncio.to_thread(wf_path.write_text, wf_data, encoding="utf-8")
                cmd.extend(["--workflow", str(wf_path)])

            cmd.extend(
                [
                    "--output",
                    str(output_path),
                    "--preset",
                    preset,
                    "--site",
                    site,
                    "--concurrency",
                    str(self.concurrency),
                ]
            )

            if verified_date:
                cmd.extend(["--date", verified_date])

            if scenes:
                # Scene lengths and caption word timings from `plan_scenes` (decision D4), per step_seq.
                scenes_path = tmp / "scenes.json"
                scenes_data = json.dumps(
                    {
                        str(sc.step_seq): {
                            "duration_ms": sc.duration_ms,
                            "words": [w.model_dump() for w in sc.words],
                        }
                        for sc in scenes
                    }
                )
                await asyncio.to_thread(scenes_path.write_text, scenes_data, encoding="utf-8")
                cmd.extend(["--scenes", str(scenes_path)])

            if manifest is not None:
                manifest_path = tmp / "manifest.json"
                manifest_data = manifest.model_dump_json(exclude_none=True)
                await asyncio.to_thread(manifest_path.write_text, manifest_data, encoding="utf-8")
                cmd.extend(["--manifest", str(manifest_path)])

            if screenshots:
                shots_path = tmp / "screenshots.json"
                shots_data = json.dumps({str(k): v for k, v in screenshots.items()})
                await asyncio.to_thread(shots_path.write_text, shots_data, encoding="utf-8")
                cmd.extend(["--screenshots", str(shots_path)])

            if audio_urls:
                audio_path = tmp / "audio.json"
                audio_data = json.dumps({str(k): v for k, v in audio_urls.items()})
                await asyncio.to_thread(audio_path.write_text, audio_data, encoding="utf-8")
                cmd.extend(["--audio", str(audio_path)])

            if vtt_path is not None:
                await asyncio.to_thread(vtt_path.parent.mkdir, parents=True, exist_ok=True)
                cmd.extend(["--vtt", str(vtt_path)])

            if metadata_path is not None:
                await asyncio.to_thread(metadata_path.parent.mkdir, parents=True, exist_ok=True)
                cmd.extend(["--metadata", str(metadata_path)])

            return await self._run_process(cmd, output_path, vtt_path, metadata_path, on_progress, timeout_s)

    def _build_base_command(self) -> list[str]:
        tsx_cli = self.package_dir / "node_modules" / "tsx" / "dist" / "cli.mjs"
        cli_ts = self.package_dir / "src" / "cli.ts"
        if tsx_cli.is_file() and cli_ts.is_file():
            return [self.node_path, str(tsx_cli), str(cli_ts)]

        pnpm = shutil.which("pnpm")
        if pnpm is not None:
            return [pnpm, "--dir", str(self.package_dir), "run", "render", "--"]

        raise RenderError("Neither tsx nor pnpm is available to drive the Remotion renderer")

    async def _run_process(
        self,
        cmd: list[str],
        output_path: Path,
        vtt_path: Path | None,
        metadata_path: Path | None,
        on_progress: Callable[[int], Awaitable[None]] | None,
        timeout_s: float,
    ) -> RenderResult:
        env = {**os.environ, "NODE_ENV": "production"}
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.package_dir),
            env=env,
        )

        stderr_lines: deque[str] = deque(maxlen=25)

        async def read_stderr() -> None:
            assert proc.stderr is not None
            while line := await proc.stderr.readline():
                stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())

        stderr_task = asyncio.create_task(read_stderr())
        duration_ms = 0

        try:
            assert proc.stdout is not None
            while True:
                line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout_s)
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                if msg_type == "progress":
                    percent = int(msg.get("percent", 0))
                    if on_progress:
                        try:
                            await on_progress(percent)
                        except Exception:
                            logger.exception("Error in render progress callback")
                elif msg_type == "completed":
                    res = msg.get("result", {})
                    duration_ms = int(res.get("durationMs", 0))
                elif msg_type == "error":
                    raise RenderError(msg.get("message", "Unknown render error"))

            await asyncio.wait_for(proc.wait(), timeout=15)
            await asyncio.wait_for(stderr_task, timeout=5)
        except TimeoutError as e:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            stderr_task.cancel()
            raise TimeoutError(f"Remotion render timed out after {timeout_s:g} s") from e
        except Exception:
            stderr_task.cancel()
            raise

        if proc.returncode != 0:
            err_msg = " | ".join(stderr_lines) or f"exit code {proc.returncode}"
            raise RenderError(f"Remotion render failed ({err_msg})")

        has_output = await asyncio.to_thread(lambda: output_path.is_file() and output_path.stat().st_size > 0)
        if not has_output:
            raise RenderError(f"Remotion rendered no output at {output_path}")

        has_vtt = await asyncio.to_thread(vtt_path.is_file) if vtt_path else False
        has_meta = await asyncio.to_thread(metadata_path.is_file) if metadata_path else False

        return RenderResult(
            output_path=output_path,
            duration_ms=duration_ms,
            vtt_path=vtt_path if has_vtt else None,
            metadata_path=metadata_path if has_meta else None,
        )

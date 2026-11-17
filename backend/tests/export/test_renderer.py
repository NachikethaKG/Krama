"""Unit tests for RemotionRenderer (#126)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.contracts_gen.common_schema import Action, ExpectedState
from app.contracts_gen.step_schema import ObservedState, Step, StepTarget, StepVerification
from app.contracts_gen.workflow_schema import Workflow, WorkflowViewport
from app.export.renderer import RemotionRenderer, RenderError

pytestmark = pytest.mark.anyio


def make_test_workflow() -> Workflow:
    return Workflow(
        id=uuid4(),
        version="1.0",
        revision=1,
        title="Renderer Test Workflow",
        target_app="gitea",
        status="verified",
        viewport=WorkflowViewport(width=1280, height=800, device_scale_factor=1.0),
        recording_path="runs/test/recording.json",
        steps=[
            Step(
                id=uuid4(),
                seq=1,
                action=Action(type="click"),
                target=StepTarget(selector="#btn", name="Button"),
                instruction_text="Click the button",
                expected_state=ExpectedState(),
                observed_state=ObservedState(url="http://gitea", title="Home", headings=[]),
                verification=StepVerification(result="verified", method=["dom"], confidence=1.0),
                risk="low",
                start_ms=0,
                end_ms=500,
            )
        ],
    )


async def test_remotion_renderer_command_construction(tmp_path: Path) -> None:
    renderer = RemotionRenderer(package_dir=tmp_path, node_path="node")
    workflow = make_test_workflow()
    output_mp4 = tmp_path / "out.mp4"

    with (
        patch.object(renderer, "_build_base_command", return_value=["node", "cli.js"]),
        patch.object(renderer, "_run_process", new_callable=AsyncMock) as mock_run,
    ):
        await renderer.render(
            output_path=output_mp4,
            preset="portrait",
            workflow=workflow,
            site="custom.domain",
        )

        mock_run.assert_awaited_once()
        cmd, out, *_ = mock_run.call_args[0]
        assert cmd[0:2] == ["node", "cli.js"]
        assert "--preset" in cmd
        assert cmd[cmd.index("--preset") + 1] == "portrait"
        assert "--site" in cmd
        assert cmd[cmd.index("--site") + 1] == "custom.domain"
        assert "--output" in cmd
        assert cmd[cmd.index("--output") + 1] == str(output_mp4)
        assert out == output_mp4


async def test_remotion_renderer_requires_spec_or_workflow(tmp_path: Path) -> None:
    renderer = RemotionRenderer(package_dir=tmp_path)
    output_mp4 = tmp_path / "out.mp4"

    with pytest.raises(ValueError, match="Either workflow or spec must be provided"):
        await renderer.render(output_path=output_mp4)


async def test_remotion_renderer_run_process_progress_and_success(tmp_path: Path) -> None:
    renderer = RemotionRenderer(package_dir=tmp_path)
    output_mp4 = tmp_path / "out.mp4"
    await asyncio.to_thread(output_mp4.write_bytes, b"dummy mp4")

    # Mock process stdout and stderr
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.wait = AsyncMock(return_value=0)

    # Stream lines: progress then completed then EOF
    lines = [
        b'{"type":"progress","percent":30}\n',
        b'{"type":"progress","percent":60}\n',
        b'{"type":"completed","result":{"durationMs":3500}}\n',
        b"",
    ]
    mock_proc.stdout.readline = AsyncMock(side_effect=lines)
    mock_proc.stderr.readline = AsyncMock(side_effect=[b""])

    progress_events: list[int] = []

    async def on_progress(p: int) -> None:
        progress_events.append(p)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await renderer._run_process(
            cmd=["node", "cli.js"],
            output_path=output_mp4,
            vtt_path=None,
            metadata_path=None,
            on_progress=on_progress,
            timeout_s=10.0,
        )

    assert result.duration_ms == 3500
    assert result.output_path == output_mp4
    assert progress_events == [30, 60]


async def test_remotion_renderer_run_process_failure_exit_code(tmp_path: Path) -> None:
    renderer = RemotionRenderer(package_dir=tmp_path)
    output_mp4 = tmp_path / "out.mp4"

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.wait = AsyncMock(return_value=1)
    mock_proc.stdout.readline = AsyncMock(side_effect=[b""])
    mock_proc.stderr.readline = AsyncMock(side_effect=[b"Fatal error: out of memory\n", b""])

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(RenderError, match="Fatal error: out of memory"),
    ):
        await renderer._run_process(
            cmd=["node", "cli.js"],
            output_path=output_mp4,
            vtt_path=None,
            metadata_path=None,
            on_progress=None,
            timeout_s=10.0,
        )
